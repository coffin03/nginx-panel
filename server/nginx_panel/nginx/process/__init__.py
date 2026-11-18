"""进程适配器工厂：根据实例配置与主配置里的 pid 指令选择实现。"""

import os
from typing import Optional

from ..ast import Node
from ..includes import ConfTree, load_tree
from .base import InstanceTarget, ProcessAdapter
from .local import LocalAdapter
from .systemd import SystemdAdapter


def detect_pid_path(tree: ConfTree, prefix: str) -> str:
    """从主配置读取 pid 指令，找不到则用 prefix/logs/nginx.pid。"""
    pid = find_directive(tree.root.nodes if tree.root else [], "pid")
    if pid and pid.args:
        value = pid.args[0]
        return value if os.path.isabs(value) else os.path.join(prefix, value)
    return os.path.join(prefix, "logs", "nginx.pid")


def find_directive(nodes, name: str) -> Optional[Node]:
    for node in nodes:
        if node.name == name:
            return node
    return None


def build_adapter(target: InstanceTarget, tree: Optional[ConfTree] = None) -> ProcessAdapter:
    if target.run_mode == "systemd":
        return SystemdAdapter(target)
    if tree is None:
        tree = load_tree(target.conf_abs, target.prefix)
    return LocalAdapter(target, detect_pid_path(tree, target.prefix))