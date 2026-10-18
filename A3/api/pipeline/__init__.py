"""The A3 chat pipeline: M1 understand -> M2 state -> M3 route -> M4 retrieve -> M5 post-process ->
M6 generate -> M7 verify, run by orchestrator.run_turn. Every ablation arm is the same code with other
flags (flags.py, CLAUDE.md rule 10)."""
