# Output-Sensitive Replacement Arrivals in Temporal Contact Streams

**Who arrives later when one contact is withdrawn?** With the deadline at time 6, recipients *a*, *b* and *c* still receive the message. Recipient *d* first receives it at time 7 and misses the deadline.

![Original and replacement arrival times for the four recipients, with a deadline at time 6.](figures/withdrawal.png)

A dependency subtree identifies the affected recipients. One depth threshold recovers their replacement times.

- **Space.** The independent time-expanded dominator index used a median of **2.48×** the component index’s retained bytes. The component index was smaller in 35 of 36 source sessions.
- **Service time.** The median ratio for the same two methods was **1.03** across nine logs. The three-run ranges overlapped on every log.

<details>
<summary>Replay the seven example queries</summary>

On x64 Windows with Python 3.10+ and Visual Studio C++ Build Tools:

~~~powershell
.\build.cmd
python run_example.py
~~~

Both indexes are checked against chronological replay.
</details>
