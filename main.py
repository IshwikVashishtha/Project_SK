import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "cli"

    if mode == "cli":
        from interfaces.cli import run_cli
        run_cli()

    elif mode == "telegram":
        from interfaces.telegram_bot import run_telegram_bot
        run_telegram_bot()

    elif mode == "whatsapp":
        from interfaces.whatsapp_bot import run_whatsapp_bot
        run_whatsapp_bot()

    else:
        print(f"Unknown mode '{mode}'. Use: cli | telegram | whatsapp")
        sys.exit(1)


if __name__ == "__main__":
    main()