import py_trees


class BlockingCondition(py_trees.decorators.Condition):
    """
    Alias class which only provides some meaning to the standard py_trees Condition class.
    As "Condition" in the BT literature is usually defined as a leaf node and not as a decorator
    which can implement loop-like Behaviour, the name can cause confusion.
    """

    pass


class LoopingDecorator(py_trees.decorators.Condition):
    """
    Alias class which only provides some meaning to the standard py_trees Condition class.
    As "Condition" in the BT literature is usually defined as a leaf node and not as a decorator
    which can implement loop-like Behaviour, the name can cause confusion.
    """

    pass
