# Short Order — a kitchen that is really an operating system

A scheduler for the Short Order arena, a simulation that dresses up a classic
computer science problem as a busy restaurant.

Orders arrive. Cooks are limited. Customers get impatient and walk out. Someone
has to decide, moment by moment, who cooks what — and that someone is this
program.

---

## The trick of it

Everything in the kitchen stands for something in an operating system. Once you
see the mapping, the restaurant stops being a metaphor and starts being a CPU.

| In the kitchen | In the machine |
| --- | --- |
| a cook | a CPU core |
| an order | a process |
| chopping, searing, plating | CPU bursts |
| the oven, the grill, resting | I/O — the dish needs nobody |
| a cook picking up a new order | a context switch, and it costs real time |
| the prep bench, the pass, the bar | locks with a fixed number of permits |
| the customer's patience | a deadline |
| the ticket rail | the ready queue |

So "which order should this cook start next?" is exactly "which process should
this core run next?" — and the wrong answer looks like a dining room emptying
out.

---

## What counts as doing well

There is no single number to chase. The scheduler is marked on six things at
once, and they disagree with each other constantly:

- **Completion** — how many customers actually got their food
- **Response** — how long before anyone so much as started their order
- **Turnaround** — how long the whole visit took
- **Slowdown** — how long it took *relative to how long it should have*
- **Switching** — how much time was burnt changing tasks instead of working
- **Fairness** — whether the pain was shared or dumped on a few unlucky tables

Serve only the quick dishes and completion looks wonderful while the banquet
table quietly starves. Rotate everybody fairly and you spend the whole service
switching and cook nothing. The interesting part is the tension.

It is also marked across **ten different kitchens** — a single cook, four
cooks, a Friday rush with more custom than anyone can serve, a night of nothing
but slow roasts, a service where the recipes are hidden, a private booking.
A strategy that only works in one of them isn't a strategy, so nothing here is
allowed to be tuned for a particular menu — the scheduler works out what kind
of kitchen it is standing in from what it can see, and adapts.

---

## The strategy

Rather than pick one textbook rule and live with its blind spot, this scheduler
scores every waiting order on several things at once and starts whichever comes
out best — a bit like how a route-finder weighs distance travelled against
distance remaining instead of trusting either alone.

**Take the quick jobs first.** Mostly. A two-minute espresso sitting behind a
forty-minute banquet is the single most expensive mistake available, so short
work gets priority — but never absolutely, because that way lies starvation.

**Let the forgotten jump the queue.** Every order carries a grudge that grows
the longer it waits, measured against how long its dish actually needs. Wait
long enough and even a banquet outranks a fresh espresso. This is what stops
the big orders from rotting on the rail forever, and it turned out to be the
single biggest improvement in the whole project.

**Clear the tiny stuff immediately.** Anything quicker than the scoring floor
gets no credit for being small — it can only ever lose by waiting. So those
jump straight to the front.

**Don't cook what can't be saved.** If the customer will have walked out before
the dish could possibly be plated, cooking it is a loss taken on purpose: they
leave anyway, and the time is stolen from someone who would have stayed. Those
orders go to the very back.

**Hold the big dishes back when the room is full.** A cook tied up on a
fifty-minute banquet is fifty minutes that every ticket behind it waits as
well. So while the rail is long, the biggest dishes sit out and wait for a
lull. They can't be stranded there — the moment a cook has nothing else to
pick up, the hold comes off and the banquet goes on.

**Never interrupt.** Taking a cook off a half-finished dish costs twice — once
to switch away, once to come back. Tempting in theory, measurably worse in
practice. Every version that preempted scored below the one that didn't.

**Watch the doorways.** Only so many cooks fit at the pass or the bar. An order
sent to a full station just bounces back, so the scheduler checks there is
somewhere to stand before it commits a cook.

**In a silent kitchen, set an alarm — then share the cooks round.** One of the
services is a private booking: the party arrives in sittings, nothing goes in
an oven, and between sittings nothing happens at all. Start a long dish there
and the kitchen has no reason to ask you anything for hundreds of ticks, so the
last table waits the whole evening before anyone even looks at them.

The fix is a timer, and it does two jobs. First it wakes the kitchen up to give
every table a moment of attention, so nobody sits ignored. Then it keeps going:
rather than finishing one dish at a time, the cooks hand over to the next table
every so often. Nobody is served especially early, but everybody waits roughly
in proportion to what they ordered — a small plate doesn't spend the evening
stuck behind a centrepiece. That evenness is worth more on this service than
the time lost handing over, and it turned a weak result into the strongest one
on the board.

---

## How it does

Scored across every kitchen, it comes out ahead of the strongest scheduler
built into the simulation — the one the exercise sets as the target to beat.

It is strongest on the private booking, where the timer earns its keep, and on
the four-cook service line. It is weakest on the Friday rush, which is designed
so that more customers arrive than two cooks can ever serve — some of those
tables were always going home hungry, and the job there is choosing which.

---

## Running it

You need Python 3.8 or newer. Nothing to install — the simulator ships with the
project.

```bash
./start.sh            # macOS and Linux
START.cmd             # Windows
```

A dashboard opens in your browser. Pick a scheduler, pick a kitchen, press
**Play & watch** and you can see the service happen — tickets on the rail,
cooks crossing the floor, dishes in the oven, and the occasional customer
giving up and leaving.

The entire scheduler is one file:
[`my-scheduler/scheduler.py`](my-scheduler/scheduler.py).
