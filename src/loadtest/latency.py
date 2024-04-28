import subprocess


NETWORK_INTERFACES = ['eno1', 'kilo0']


def setup_latency(latency_ms: float):
    for itf in NETWORK_INTERFACES:
        cmd = ([
            'sudo',
            'tc',
            'qdisc',
            'add',
            'dev',
            f'{itf}',
            'root',
            'netem',
            'delay',
            f'{latency_ms}ms',
            ])
        subprocess.run(cmd)
        print("[setup_latency]", cmd)


def remove_latency():
    for itf in NETWORK_INTERFACES:
        cmd = ([
            'sudo',
            'tc',
            'qdisc',
            'del',
            'dev',
            f'{itf}',
            'root',
            'netem',
            ])
        subprocess.run(cmd)
        print("[remove_latency]", cmd)
