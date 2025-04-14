import time
from module_folder import some_function2
from module_folder import nested_function

# simulate a long-running process
time.sleep(1)


def some_function():
    print("This is a function in another module.")
    some_function2()
    nested_function()
