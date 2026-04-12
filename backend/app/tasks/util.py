from termcolor import colored


def colored_print(text, color: str):
    print(colored(text, color))


def print_warning(text):
    colored_print(text, "yellow")


def print_error(text):
    colored_print(text, "red")


def print_success(text):
    colored_print(text, "green")
