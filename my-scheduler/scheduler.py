"""Ranks the rail on four things at once: the next burst length, the total work
left, how long the customer has already been sitting relative to what their food
needs, and whether the next step lands on a full station. Lowest total gets the
next free cook; orders that can no longer be finished in time go to the back.
With no ovens to wake us it slices instead, so nobody sits unlooked-at.
"""

from kitchen import Decision, Scheduler, fill_idle


def _saturate(value, scale):
    """Squash onto [0, 1), bigger being worse. `scale` scores 0.5."""
    if value <= 0.0:
        return 0.0
    return value / (value + scale)


class MiseEnPlace(Scheduler):
    name = "mise_en_place"
    version = "5"

    W_BURST = 0.45          # shortest job first
    W_REMAINING = 0.45      # shortest remaining time first
    W_BUMP = 0.20           # penalty for a next step at a full station
    W_AGE = 0.60            # discount for an order already kept waiting

    # Half-way point of each term, so a typical order sits in the middle of the
    # curve rather than out on a flat end of it. The first two are ticks; K_AGE
    # is a slowdown, the same figure the mark is worked out from.
    K_BURST = 8.0
    K_REMAINING = 20.0
    K_AGE = 6.0

    # Only read the next station when the step in hand is this close to done;
    # any further out and it will have turned over before we get there.
    BUMP_HORIZON = 4.0

    # Big enough to put the hopeless orders behind every servable one without
    # losing their order among themselves.
    DOOMED_COST = 10.0

    # Slicing, for kitchens that will not call us back on their own. A slice is
    # one tick: it exists only to get a first tick of work onto every order, and
    # nothing is gained by making it longer. 0 turns slicing off.
    ROTATE_QUANTUM = 1
    ROTATE_MIN_BURST = 12

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

    def _total_span(self, obs, order):
        """The whole time this dish needs, work and oven together. The mark
        divides turnaround by this, floored at the kitchen's own bound."""
        done = 0.0
        for step in order.steps[:order.step]:
            if step.duration is not None:
                done += step.duration
        return done + self._remaining_span(obs, order)

    def _pressure(self, obs, order):
        """The slowdown this order has run up already: how long the customer
        has been sitting there, over the time their food actually needs.

        Shortest-job-first on its own starves the long orders, and the mark
        takes the evenness of these figures as its fairness score - so the one
        with the worst of them is the one to start next, other things equal."""
        span = max(self._total_span(obs, order), obs.kitchen.slowdown_bound)
        return (obs.time - order.arrival) / span

    def _bump_risk(self, obs, order):
        """1.0 when this order is about to finish its step and move to a station
        with no place free. That sends it back to the rail and costs a second
        switch to pick it up again."""
        nxt = order.step + 1
        if nxt >= len(order.steps):
            return 0.0
        name = order.steps[nxt].station
        if name is None:
            return 0.0                      # the oven needs no place
        step = order.current_step
        if step is None or step.remaining is None:
            return 0.0
        if step.remaining > self.BUMP_HORIZON:
            return 0.0
        station = obs.station(name)
        if station is None:
            return 0.0
        return 0.0 if station.free > 0 else 1.0

    # -- the composite cost -------------------------------------------------

    def _cost(self, obs, order, switch_cost):
        """Four costs in [0, 1), added by weight. Lowest wins."""
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
            + self.W_BUMP * self._bump_risk(obs, order)
            - self.W_AGE * _saturate(self._pressure(obs, order), self.K_AGE)
        )
        if doomed:
            cost += self.DOOMED_COST
        return cost, doomed

    # -- rotation -----------------------------------------------------------

    def _event_starved(self, obs):
        """Whether anything will call us back on its own. No dish in an oven and
        none due to go in one means the engine has nothing to report until
        something finishes, so an alarm is the only way to be asked again.

        The menu settles it first: one oven step anywhere on it and this kitchen
        hands out free wake-ups all service, even if nothing happens to be in an
        oven this instant."""
        for recipe in obs.recipes.values():
            for _, kind, _ in recipe.steps:
                if kind == "wait":
                    return False
        for order in obs.orders:
            if order.is_blocked:
                return False
            for step in order.steps_left:
                if step.is_wait:
                    return False
        return True

    def _should_rotate(self, obs, rail):
        """Whether to hand out slices instead of running orders to completion.

        Only once the door has been shut a while, and only when a slice is short
        next to the jobs on the rail - with a one-tick espresso waiting, slicing
        changes nobody's turn and just spends switches."""
        if self.ROTATE_QUANTUM <= 0 or len(rail) <= len(obs.cores):
            return False
        # Only the orders nobody has looked at yet. Judging this on the whole
        # rail switches rotation off the moment it starts, because the order it
        # just preempted comes back part-done and short.
        waiting = [order for order in rail if not order.has_started]
        if not waiting:
            return False
        floor = self.ROTATE_MIN_BURST + obs.kitchen.switch_cost
        return min(self._burst(obs, order) for order in waiting) > floor

    def _rotate(self, obs, decision, rail):
        """Give each cook that has had its slice the next never-started order.

        Response is measured at the first tick of work, so one sweep across the
        rail banks it - after that everybody has been looked at and the cooks
        run their orders out."""
        unstarted = [o for o in rail if not o.has_started]
        started = [o for o in rail if o.has_started]
        free = obs.free_stations()
        for core in obs.cores:
            current = obs.order_on(core)
            if current is not None and core.running_for < self.ROTATE_QUANTUM:
                continue                    # mid-slice, leave it alone
            if unstarted:
                queue = unstarted
            elif current is None:
                queue = started             # idle cook, nobody new to look at
            else:
                continue                    # sweep done; let it run out
            if core.station:
                free[core.station] = free.get(core.station, 0) + 1
            for index, order in enumerate(queue):
                station = order.station
                if station is not None and free.get(station, 0) <= 0:
                    continue
                decision.assign(core, order)
                if station is not None:
                    free[station] -= 1
                queue.pop(index)
                break
            else:
                if core.station:
                    free[core.station] -= 1  # took nothing; keeps its place

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
        starved = bool(rail) and self._event_starved(obs)
        rotating = starved and self._should_rotate(obs, rail)
        if rotating:
            self._rotate(obs, decision, rail)
        else:
            # Walks the rail in order, skipping anything whose station is full
            # and counting places as it spends them.
            fill_idle(decision, obs, rail)
        if starved and any(not order.has_started for order in rail):
            # Nothing else is going to ask us, and somebody has not been looked
            # at yet - so set the alarm even if it is too early to slice.
            decision.wake_in(self.ROTATE_QUANTUM)

        note = "slicing" if rotating else "running out"
        return decision.annotate(
            text=f"{len(rail)} on the rail, {len(doomed_ids)} past saving, {note}",
            queue=[order.id for order in rail],
            tags={order_id: "cannot finish in time" for order_id in doomed_ids[:12]},
        )
