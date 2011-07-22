# Configuration tree for Kitero.

default = {
    'web': {
        # Web interface should listen to this IP:port
        'listen': '0.0.0.0',
        'port': 8187,
        'debug': False,
        'expire': 15*60,        # Expire unalive clients after 15 minutes
        },
    'helper': {
        # Helper application should listen to this IP:port
        'listen': '127.0.0.1',
        'port': 18861,
        }
    }

def merge(config={}, default=default):
    """Merge the default configuration with the given configuration.

    :param config: configuration to merge with default configuration
    :type config: dictionary
    :return: merged configuration
    """
    import copy
    def _merge(first, second):
        # Merge two dictionaries. Lot of copies.
        # Do simple cases faster.
        if not first:
            return copy.deepcopy(second)
        result = copy.deepcopy(first)
        if not second:
            return result
        if type(second) is not dict and type(first) is not dict:
            return second
        if type(second) is not dict or type(first) is not dict:
            raise ValueError("conflicting merge")
        for key in second:
            if key not in result:
                result[key] = copy.deepcopy(second[key])
            else:
                result[key] = _merge(result[key], second[key])
        return result
    return _merge(default, config)
