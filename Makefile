.PHONY: sample meta control score-control metadata score-metadata recall

sample:          ; python -m src.build_sample
meta:            ; python -m src.fetch_metadata
control:         ; python -m src.run_arm --arm control --model claude
                   python -m src.run_arm --arm control --model gpt
score-control:   ; python -m src.score --arm control
metadata:        ; python -m src.run_arm --arm metadata --model claude
                   python -m src.run_arm --arm metadata --model gpt
score-metadata:  ; python -m src.score --arm metadata
recall:          ; python -m src.run_arm --arm recall --model claude --limit 30
