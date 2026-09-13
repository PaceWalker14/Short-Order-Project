# Short Order — scheduler project

This repository contains a Python scheduler for the Short Order arena, an
educational simulation that models a restaurant kitchen as a computer system.
The goal is to decide which orders each cook should work on so that more
customers are served quickly, with fewer unnecessary context switches and a
fairer distribution of waiting time.

The project is also a local copy of the course platform: it includes the
simulation engine, service profiles, Python SDK, dashboard, and student guide.
The only file intended for submission is
[`my-scheduler/scheduler.py`](my-scheduler/scheduler.py).

Nothing to install and nothing to build. You need **Python 3.8 or newer** and
nothing else — the simulation engine is already compiled and included for
Windows, macOS and Linux.

---

## Start here

**Windows** — double-click `START.cmd` (the bundled engine must match your
platform; this copy currently includes the Linux engine).

**macOS and Linux** — open a terminal in this folder and run:

```bash
bash start.sh
```

After the first run `./start.sh` works too. (Some unzip tools drop the
executable bit; the first run puts it back.)

Your browser opens the dashboard. Pick a scheduler, pick a service, press
**Play & watch**. That is the whole loop.

If something looks wrong, run `START.cmd doctor` (or `./start.sh doctor`) and
it will tell you what it found.

---

## Writing your scheduler

Your scheduler is [`my-scheduler/scheduler.py`](my-scheduler/scheduler.py).
One file, and that file *is* your submission — what you debug here is exactly
what you hand in.

```text
my-scheduler/
  scheduler.py      all of your code, in this one file
```

Open it and edit it. It is already a working, intentionally weak baseline: it
starts the longest available job first and may preempt a shorter job for an
even longer one. Change one policy decision at a time and measure whether it
helped.

**All of your code goes in `scheduler.py`.** A second `.py` file next to it
will not be importable when the server loads your scheduler, so it is rejected
rather than quietly ignored. Check at any time with:

```bash
START.cmd check my-scheduler        # Windows
./start.sh check my-scheduler       # macOS and Linux
```

which runs the marker's own checks: the folder's structure, and then your
scheduler actually running a service on every public seed.

When you are done, **upload `my-scheduler/scheduler.py` to Moodle**. That is
the whole hand-in: no zip, no folder, nothing to fill in — Moodle already knows
who you are, and that is where your name on the leaderboard comes from.

### The picture

Cooks are CPU cores. Orders are processes. A recipe's `work` steps are CPU
bursts, and its `wait` steps — the oven — are I/O bursts. Every customer has
a patience: an order not served by its deadline walks out. You are the
scheduler: the engine calls you at every scheduling point and you say which
order each cook should be working on. Every time a cook takes on an order it
pays a context switch of `obs.kitchen.switch_cost` ticks, so changing your
mind is not free.

You implement one method:

```python
from kitchen import Decision, Scheduler


class MyScheduler(Scheduler):
    name = "my_scheduler"
    version = "1"

    def schedule(self, obs):
        return Decision()      # names no cook, so nobody cooks: scores zero
```

That is the whole interface. The filled-in version is the
`my-scheduler/scheduler.py` in this download — read its comments before you
change anything. It is the only scheduler here whose source you get: the
references are compiled into the engine, so you can play them and measure them
but not copy them.

`schedule` runs whenever something happens — service opens, an order arrives,
a cook comes free, an order comes back from the oven, a customer walks out, or
an alarm you set goes off. `obs.reason.kinds` says which. Deciding who cooks
what — and whether to take a cook off what it is doing — is the assignment.

The parts of `obs` you will use most:

| | |
|---|---|
| `obs.time` | now, in ticks |
| `obs.ready` | orders waiting for a cook, oldest first |
| `obs.idle_cores` | cooks with nothing to do |
| `obs.working_cores` | cooks mid-order (`core.order` is the order id) |
| `order.work_remaining` | ticks of work left (`None` when durations are hidden) |
| `order.time_left` | ticks until the customer walks out |
| `order.priority` | 1 regular, 2 hurried, 3 VIP |
| `obs.estimate_remaining(order)` | a guess at the work left when it is hidden |

And of `Decision`:

| | |
|---|---|
| `d.assign(core, order)` | put this order on this cook (preempts whatever it held) |
| `d.idle(core)` | take the cook off its order |
| `d.wake_in(ticks)` | call me again in this many ticks — your timer interrupt |
| `d.annotate(text=..., queue=[...], tags={...})` | drawn by the viewer, ignored by the engine |

A cook you do not mention carries on. An order you do not mention waits.

You are scored on six things, and `play` prints all six: completion, response
time, turnaround time, slowdown, switching efficiency, and fairness.

The full API — every field on `obs`, every method on `Decision`, the scoring —
is in [`docs/student-guide.md`](docs/student-guide.md).

The scheduler to read is the one you already have:
[`my-scheduler/scheduler.py`](my-scheduler/scheduler.py). Its comments explain
every move it makes, including the station-counting trap that catches everyone
once. There is no second worked example on purpose — the other policies ship
compiled into the engine, so `compare` will tell you how far short you are
without telling you how they got there.

---

## Running from the command line

The dashboard is easier, but the command line gives you numbers and repeats.

Every command below is written `./start.sh …`, which is the macOS and Linux
form. **On Windows write `START.cmd …` instead** — the arguments after it are
identical on all three platforms, and so are the results. Name your scheduler
by its **folder**:

```bash
./start.sh play my-scheduler --seed 7               # one service, with statistics
./start.sh play my-scheduler --config rush          # a different service profile
./start.sh play my-scheduler --replay               # record it, then watch it
./start.sh check my-scheduler                       # is my submission complete?
./start.sh validate my-scheduler                    # the acceptance checks alone
./start.sh evaluate my-scheduler --seeds 1000..1020 # a whole seed set, summarised
./start.sh compare my-scheduler                     # you against every reference scheduler
./start.sh baselines                                # the reference schedulers, described
./start.sh workload --seed 7                        # the orders a seed produces
```

`check` is the one to run before you hand anything in. It applies the same
checks the marking pipeline does — that your scheduler is one file called
`scheduler.py`, and that it loads, runs legally and keeps inside the 50 ms
per-decision deadline on every public seed — so a submission that passes here
is one the marker will accept.

One seed is one lunch service. `evaluate` plays a whole set of seeds and
reports the mean and the spread, which is the number worth paying attention
to. `compare` does the same for you and every reference scheduler at once, on
the same seeds. The reference schedulers are named after kitchen characters,
and the name tells you nothing about the algorithm - the textbook name in
brackets is the one to look up:
`middle_management` (fifo), `headless_chicken` (round robin), `julia_child` (sjf), `sous_chef`
(srtf), `stickler` (priority), `trainee` (edf), `portion_control` (stride)
and `smoke_break` (mlfq) — and `gordon_ramsay` is the one to beat — plus
`idiot_sandwich`, which is your `scheduler.py` as it arrived, and `maitre_d`
and `dishwasher` for a sense of the floor. Any of them can be named
wherever a scheduler is asked for: `./start.sh play gordon_ramsay --seed 7`.
The textbook name in brackets works too, so `play sjf` and `play julia_child`
are the same scheduler.

The marker uses hidden seeds; the public practice seeds are 1001 to 1005.

### Service profiles

`configs/` holds the services you can run, and `--config` picks one by name:

| profile | what it is for |
|---|---|
| `default` | the course profile, "lunch service" — every run is marked under these rules |
| `rush` | more custom than two cooks can serve; somebody walks out whatever you do |
| `one-cook` | a single core: the textbook setting, where the classic algorithms behave as the diagrams say |
| `brigade` | four cooks and a full room |
| `banquet-night` | long jobs in front of short ones — the convoy effect |
| `bake-off` | nearly everything spends its life in the oven — I/O-bound processes |
| `blind` | the course menu with step durations hidden; `work_remaining` is `None` |

### Trying an idea without breaking your submission

Make a second scheduler folder and run the two against the same seeds:

```bash
./start.sh new second-try                           # a fresh, valid submission
./start.sh play second-try --seed 7
./start.sh play my-scheduler --seed 7
```

Both folders appear in the dashboard too, under **Your schedulers**.

---

## Watching your scheduler work

Runs are deterministic: the same scheduler, profile and seed always produce
exactly the same service. That is what makes debugging possible.

In the dashboard your schedulers are listed first, under **Your schedulers** —
pick one, pick a service, and choose **Play & watch**. It runs the service,
saves the recording to `replays/`, and opens it in the kitchen viewer, where
you can pause, step a tick at a time, and see what each cook was doing and
which orders were about to walk out. From the command line, `play … --replay`
does the same thing.

`annotate` is how you get your own reasoning on screen: label the rail with
the order you would serve it in, tag the orders you are about to preempt for,
and the viewer draws it. The starter's `annotate` call shows the shape.

---

## What is not in this download

This is the local practice environment. It deliberately leaves out the league
infrastructure, the results website and the marking pipeline, which run on the
course server.

Your scheduler file is the whole submission, so nothing here is missing from
what you hand in.

---

## Troubleshooting

**"Python 3.8 or newer was not found"** — install it from
<https://www.python.org/downloads/>. On Windows, tick *Add python.exe to PATH*
in the installer.

**"No engine bundled for this machine"** — the download does not contain a
build for your platform. On a Mac this usually means one of two things: an
Intel Mac, which has no build here — say so when you ask, and one can be made
— or an Apple Silicon Mac running an Intel build of Python under Rosetta, in
which case install the Apple Silicon build of Python from python.org. On any
platform, say which platform `doctor` reports when you ask.

**"Permission denied" running ./start.sh** — the unzip tool dropped the
executable bit. Run `bash start.sh` instead; it puts the bit back, and
`./start.sh` works from then on.

**macOS says the engine "cannot be opened"** — macOS quarantines anything
downloaded through a browser, and the engine is not notarised by Apple.
`start.sh` clears that tag for this folder every time it runs, so start with
`bash start.sh` rather than calling `python3 launch.py` yourself. To clear it
by hand, from a terminal inside this folder:

```bash
xattr -dr com.apple.quarantine .
```

**Linux: "version `GLIBC_2.xx' not found"** — your distribution is older than
the one the engine was built on. Say which distribution and version you are on
when you ask.

**"The engine is in use"** — something from this folder is still running: a
dashboard, a run, a Python prompt. Close it and try again.

**A change to your scheduler made no difference** — check you saved the file,
and that you are running `my-scheduler` and not an example or a reference
scheduler.

**"scheduler.py is missing"** — a scheduler is a folder with a `scheduler.py`
in it, and that is the name the marker loads. Run `./start.sh new <name>` to
get a valid one.

**"… is a second Python file"** — everything has to be in `scheduler.py`. Move
the code into it; a helper module next to it cannot be imported on the server.

**Anything else** — run `./start.sh doctor` and include its output when you ask.
