import os
from pathlib import Path

def reset():
    for f in ["agent1.log", "agent2.log", "agent3.log"]:
        if Path(f).exists():
            open(f, 'w').close()
    #print("System reset.")

if __name__ == "__main__":
    reset()