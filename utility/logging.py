

def log(message: str):
    with open("agent.log", "w") as f:
        f.write(message)
