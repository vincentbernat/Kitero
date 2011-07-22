Installation of Kitérő
======================

Kitérő is a pure Python application. It comes with a standard
``setup.py`` file that follow standard conventions for
installation. It can therefore be installed with the following
command::

   $ sudo python setup.py install

However, to avoid any compatibility problem, it is recommended to use
``virtualenv`` instead.

Requirements
------------

The following components are required:

* 2.6 kernel with the following options enabled:

 * ``CONFIG_IP_ADVANCED_ROUTER``
 * ``CONFIG_IP_MULTIPLE_TABLES``
 * ``CONFIG_NETFILTER``
 * ``CONFIG_NF_CONNTRACK``, ``CONFIG_NF_CONNTRACK_MARK``,
   ``CONFIG_NETFILTER_XT_MARK``, ``CONFIG_NETFILTER_XT_CONNMARK``,
   ``CONFIG_NETFILTER_XT_SET``,
   ``CONFIG_NETFILTER_XT_TARGET_CLASSIFY``,
   ``CONFIG_NETFILTER_XT_TARGET_CONNMARK``,
   ``CONFIG_NETFILTER_XT_MATCH_CONNMARK``, ``CONFIG_IP_NF_MANGLE``
 * ``CONFIG_NET_SCHED``, ``CONFIG_NET_SCH_PRIO``,
   ``CONFIG_NET_SCH_TBF``, ``CONFIG_NET_SCH_NETEM``,
   ``CONFIG_NET_SCH_DRR``, ``CONFIG_NET_EMATCH_U32``

* A version of `iproute` matching the kernel (this brings ``ip`` and
  ``tc`` commands).
* ``iptables``.
* Python 2.6 or 2.7.

Installing with ``virtualenv``
------------------------------

Installation of virtualenv
``````````````````````````

One of the following commands should do the trick::

    $ sudo apt-get install python-virtualenv
    $ sudo pip install virtualenv
    $ sudo easy_install virtualenv

Setting up virtualenv
`````````````````````

Once virualenv is installed, the an isolated environment can be
setup::

    $ mkdir env
    $ cd env
    $ virtualenv -p /usr/bin/python2.6 --no-site-packages env
    Running virtualenv with interpreter /usr/bin/python2.6
    New python executable in env/bin/python2.6
    Also creating executable in env/bin/python
    Installing distribute......done.
    $ cd ..

We can now enable this new environment with::

    $ . env/bin/activate

Installing Kitérő
`````````````````

Once in the newly created environment, installing Kitérő is quite
easy. We need to install the required dependencies that are listed in
``requirements.txt`` and install Kitérő::

    $ pip install -r requirements.txt
    $ python setup.py install
