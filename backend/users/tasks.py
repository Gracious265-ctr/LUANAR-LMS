def ping():
    """Trivial task to verify the worker can pick up and execute tasks.

    Dispatch via: async_task("users.tasks.ping")
    """
    return "pong"
