# Output-Sensitive Replacement Arrivals in Temporal Contact Streams

For a fixed source and release, the index reports whom a withdrawn contact delays and when each recipient can first be reached again. A dependency subtree selects the recipients and a shared depth threshold recovers their replacement arrivals.

## Run

64-bit Windows, Python 3.10+ and Visual Studio C++ Build Tools.

~~~powershell
.\build.cmd
python run_example.py
~~~

[Data](data) includes timestamped contacts, withdrawal queries, 54 matched runs and retained-space measurements for 36 source sessions.
