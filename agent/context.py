import json

from agent.tools import get_fitness_context


def main():
    print(
        json.dumps(
            get_fitness_context(),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
