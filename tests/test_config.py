try:
    import unittest2 as unittest
except ImportError:
    import unittest

import kitero.config

class TestConfigMerge(unittest.TestCase):
    def test_merge_empty(self):
        """Merge two empty configs"""
        self.assertEqual(kitero.config.merge(config={}, default={}),
                         {})

    def test_merge_only_one_empty(self):
        """Merge two config, one of them is empty"""
        sample = {'router': {'clients': 'eth0'}}
        self.assertEqual(kitero.config.merge(config=sample, default={}),
                         sample)
        self.assertEqual(kitero.config.merge(config={}, default=sample),
                         sample)

    def test_simple_merge(self):
        """Simple merge of config"""
        self.assertEqual(kitero.config.merge(
                config={'router': {'clients': 'eth0'}},
                default={ 'web': { 'listen': '0.0.0.0',
                                   'port': 8187 }}),
                         {'router': {'clients': 'eth0'},
                          'web': { 'listen': '0.0.0.0',
                                   'port': 8187 }})

    def test_override_default(self):
        """Test overriding defaults"""
        self.assertEqual(kitero.config.merge(
                config={'router': {'clients': 'eth0'} },
                default={'router': {'clients': 'eth1'} }),
                         {'router': {'clients': 'eth0'} })

    def test_nested_merge(self):
        """Test nested merge"""
        self.assertEqual(kitero.config.merge(
                config={'router': {'clients': 'eth0'},
                        'web': { 'extra': { 'moreextra': 'spicy' }}},
                default={ 'web': { 'listen': '0.0.0.0',
                                   'port': 8187 }}),
                         {'router': {'clients': 'eth0'},
                          'web': { 'listen': '0.0.0.0',
                                   'port': 8187,
                                   'extra': { 'moreextra': 'spicy' }}})
        self.assertEqual(kitero.config.merge(
                config={'router': {'clients': 'eth0',
                                   'interface': {
                            'eth4': "Goog",
                            'eth5': "Great"
                            }},
                        'web': { 'extra': { 'moreextra': 'spicy' }}},
                default={ 'web': { 'listen': '127.0.0.1',
                                   'port': 8187 }}),
                         {'router': {'clients': 'eth0',
                                     'interface': {
                        'eth4': "Goog",
                        'eth5': "Great" } },
                          'web': { 'listen': '127.0.0.1',
                                   'port': 8187,
                                   'extra': { 'moreextra': 'spicy' }}})
        self.assertEqual(kitero.config.merge(
                default={'router': {'clients': 'eth0',
                                   'interface': {
                            'eth4': "Goog",
                            'eth5': "Great"
                            }},
                        'web': { 'extra': { 'moreextra': 'spicy' }}},
                config={ 'web': { 'listen': '127.0.0.1',
                                   'port': 8187 }}),
                         {'router': {'clients': 'eth0',
                                     'interface': {
                        'eth4': "Goog",
                        'eth5': "Great" } },
                          'web': { 'listen': '127.0.0.1',
                                   'port': 8187,
                                   'extra': { 'moreextra': 'spicy' }}})
        self.assertEqual(kitero.config.merge(
                default={'router': {'clients': 'eth0',
                                   'interface': {
                            'eth4': "Goog",
                            'eth5': "Great"
                            }},
                        'web': { 'extra': { 'moreextra': 'spicy' }}},
                config={ 'web': { 'listen': '127.0.0.1',
                                   'port': 8187 },
                         'router': { 'clients': 'eth4' } }),
                         {'router': {'clients': 'eth4',
                                     'interface': {
                        'eth4': "Goog",
                        'eth5': "Great" } },
                          'web': { 'listen': '127.0.0.1',
                                   'port': 8187,
                                   'extra': { 'moreextra': 'spicy' }}})
        self.assertEqual(kitero.config.merge(
                default={'router': {'clients': 'eth0',
                                   'interface': {
                            'eth4': "Goog",
                            'eth5': "Great"
                            }},
                        'web': { 'extra': { 'moreextra': 'spicy' }}},
                config={ 'web': { 'listen': '127.0.0.1',
                                   'port': 8187 },
                         'router': { 'clients': 'eth4',
                                     'interface': { 'eth6': 'Bling' } } }),
                         {'router': {'clients': 'eth4',
                                     'interface': {
                        'eth4': "Goog",
                        'eth6': 'Bling',
                        'eth5': "Great" } },
                          'web': { 'listen': '127.0.0.1',
                                   'port': 8187,
                                   'extra': { 'moreextra': 'spicy' }}})

    def test_conflict(self):
        """Test conflicting merge"""
        with self.assertRaises(ValueError):
            kitero.config.merge(default={'router': { 'clients': 'eth0' }},
                                config={'router': 'eth1' })
