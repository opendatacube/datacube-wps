from functools import wraps

from timeit import default_timer

def log_call(func):
    @wraps(func)
    def log_wrapper(*args, **kwargs):
        name = func.__name__
        for index, arg in enumerate(args):
            try:
                arg_name = func.__code__.co_varnames[index]
            except:
                arg_name = f'arg #{index}'
            print(f'{name} {arg_name}: {arg}')
        for key, value in kwargs.items():
            print(f'{name} {key}: {value}')
        start = default_timer()
        result = func(*args, **kwargs)
        end = default_timer()
        print('{} returned {}'.format(name, result))
        print('{} took {:.3f}s'.format(name, end - start))
        return result

    return log_wrapper
