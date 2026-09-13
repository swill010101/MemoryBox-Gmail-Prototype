# FlightSim — migration 036 is not authorized to apply

**Status:** SQL is on `codex/p2-i14-communications`. **Do not checkout FlightSim onto this SHA for serve. Do not run `python -m memorybox migrate` for 036. Do not load rows.**

Empty prepared-email tables exist only as a repository file. Applying them is a later founder gate, same pattern as 035.

If this branch is checked out on FlightSim, `/health` will show pending `036_p2_i14_prepared_communications.sql`. That is not authorization to apply it. Keep production serve on the currently authorized runtime SHA until a separate apply authorization is issued.
