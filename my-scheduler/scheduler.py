"""Scores every ready order on three things at once and dispatches the best:
the next burst length (SJF), the total work left (SRTF), and how much slack the
customer has before they walk (EDF). Each is squashed onto [0, 1) so they can be
added, and the lowest total gets the next free cook. Orders that cannot be
finished before their deadline go to the back. Nothing is ever preempted.
"""

from kitchen import Decision, Scheduler, fill_idle


def _saturate(value, scale):
    """Squash onto [0, 1), bigger being worse. `scale` scores 0.5."""
    if value <= 0.0:
        return 0.0
    return value / (value + scale)


class MiseEnPlace(Scheduler):
    name = "mise_en_place"
    version = "2"

    W_BURST = 0.45          # shortest job first
    W_REMAINING = 0.30      # shortest remaining time first
    W_SLACK = 0.25          # earliest deadline first

    # Half-way point of each term, in ticks: roughly the median of the thing
    # being measured, so a typical order sits in the middle of the curve.
    K_BURST = 8.0
    K_REMAINING = 20.0
    K_SLACK = 60.0

    # Big enough to put the hopeless orders behind every servable one without
    # losing their order among themselves.
    DOOMED_COST = 10.0

    def reset(self, seed):
        self._wait_means = {}

    # -- estimation ---------------------------------------------------------

    def _mean_wait_step(self, obs, recipe):
        """Mean oven step for this recipe, from what has been served so far.
        Only used on blind, where the steps will not say how long they are."""
        cached = self._wait_means.get(recipe)
        if cached is not None:
            return cached
        total = 0.0
        count = 0
        for entry in obs.history:
            if entry.recipe != recipe:
                continue
            for _, kind, duration in entry.steps:
                if kind == "wait" and duration is not None:
                    total += duration
                    count += 1
        mean = (total / count) if count else 20.0
        self._wait_means[recipe] = mean
        return mean

    def _remaining_span(self, obs, order):
        """Soonest this could possibly be served: every work step left plus
        every oven step left, with nobody ever waiting for a cook. This is what
        the deadline has to be measured against - work_remaining on its own
        calls a soup with fifty ticks of simmer left comfortably in time."""
        span = 0.0
        hidden_work = False
        hidden_waits = 0
        for step in order.steps_left:
            if step.remaining is not None:
                span += step.remaining
            elif step.is_work:
                hidden_work = True
            else:
                hidden_waits += 1
        if hidden_work:
            # Blind: estimate_remaining covers all the work in one go.
            span += obs.estimate_remaining(order)
        if hidden_waits:
            span += hidden_waits * self._mean_wait_step(obs, order.recipe)
        return span

    def _burst(self, obs, order):
        """Cook time before this order next lets go of its cook."""
        burst = order.work_until_wait
        if burst is None:
            return obs.estimate_remaining(order)
        return float(burst)

    # -- the composite cost -------------------------------------------------

    def _cost(self, obs, order, switch_cost):
        """Three costs in [0, 1), added by weight. Lowest wins."""
        burst = self._burst(obs, order)
        remaining = obs.estimate_remaining(order)
        span = self._remaining_span(obs, order)

        # Spare time once the dish's own time is paid for. Negative means the
        # customer is gone before it is plated whoever starts it.
        slack = order.time_left - span - switch_cost
        doomed = slack < 0.0

        cost = (
            self.W_BURST * _saturate(burst, self.K_BURST)
            + self.W_REMAINING * _saturate(remaining, self.K_REMAINING)
            + self.W_SLACK * _saturate(slack, self.K_SLACK)
        )
        if doomed:
            cost += self.DOOMED_COST
        return cost, doomed

    # -- the decision -------------------------------------------------------

    def schedule(self, obs):
        self._wait_means = {}
        switch_cost = obs.kitchen.switch_cost

        scored = []
        doomed_ids = []
        for order in obs.ready:
            cost, doomed = self._cost(obs, order, switch_cost)
            scored.append((cost, order.id, order))
            if doomed:
                doomed_ids.append(order.id)
        # Ties break on id, so equal orders go first come first served.
        scored.sort(key=lambda row: (row[0], row[1]))
        rail = [row[2] for row in scored]

        decision = Decision()
        # Walks the rail in order, skipping anything whose station is full and
        # counting places as it spends them.
        fill_idle(decision, obs, rail)

        return decision.annotate(
            text=f"{len(rail)} on the rail, {len(doomed_ids)} past saving",
            queue=[order.id for order in rail],
            tags={order_id: "cannot finish in time" for order_id in doomed_ids[:12]},
        )
