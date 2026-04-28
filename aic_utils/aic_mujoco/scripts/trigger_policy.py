#!/usr/bin/env python3
"""
MuJoCo용 정책 트리거 스크립트.

aic_engine 없이 aic_model 노드의 lifecycle을 직접 관리하고
insert_cable 액션 goal을 수동으로 전송합니다.

사용법:
    python3 trigger_policy.py
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from lifecycle_msgs.srv import GetState, ChangeState
from lifecycle_msgs.msg import Transition

from aic_task_interfaces.action import InsertCable
from aic_task_interfaces.msg import Task


MODEL_NODE_NAME = "aic_model"

# sample_config.yaml trial_1의 task_1 내용
TASK = Task(
    id="mujoco_task_1",
    cable_type="sfp_sc",
    cable_name="cable_0",
    plug_type="sfp",
    plug_name="sfp_tip",
    port_type="sfp",
    port_name="sfp_port_0",
    target_module_name="nic_card_mount_0",
    time_limit=180,
)


class PolicyTrigger(Node):
    def __init__(self):
        super().__init__("policy_trigger")
        self._get_state = self.create_client(
            GetState, f"/{MODEL_NODE_NAME}/get_state"
        )
        self._change_state = self.create_client(
            ChangeState, f"/{MODEL_NODE_NAME}/change_state"
        )
        self._action_client = ActionClient(
            self, InsertCable, "/insert_cable"
        )

    def _transition(self, transition_id: int, label: str):
        req = ChangeState.Request()
        req.transition = Transition(id=transition_id)
        future = self._change_state.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        if future.result() and future.result().success:
            self.get_logger().info(f"Transition '{label}' succeeded.")
        else:
            raise RuntimeError(f"Transition '{label}' failed.")

    def _get_current_state(self) -> str:
        req = GetState.Request()
        future = self._get_state.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        return future.result().current_state.label

    def run(self):
        self.get_logger().info("Waiting for lifecycle services...")
        self._get_state.wait_for_service(timeout_sec=30.0)
        self._change_state.wait_for_service(timeout_sec=30.0)

        state = self._get_current_state()
        self.get_logger().info(f"Current aic_model state: '{state}'")

        # 1. configure (unconfigured 상태일 때만)
        if state == "unconfigured":
            self.get_logger().info("Configuring aic_model...")
            self._transition(Transition.TRANSITION_CONFIGURE, "configure")
            state = "inactive"

        # 2. activate (inactive 상태일 때만)
        if state == "inactive":
            self.get_logger().info("Activating aic_model...")
            self._transition(Transition.TRANSITION_ACTIVATE, "activate")
        elif state == "active":
            self.get_logger().info("aic_model already active, sending goal directly.")

        # 3. insert_cable action 전송
        self.get_logger().info("Waiting for insert_cable action server...")
        self._action_client.wait_for_server(timeout_sec=10.0)

        goal = InsertCable.Goal(task=TASK)
        self.get_logger().info(f"Sending insert_cable goal: {TASK.id}")
        send_future = self._action_client.send_goal_async(
            goal,
            feedback_callback=self._feedback_cb,
        )
        rclpy.spin_until_future_complete(self, send_future)
        goal_handle = send_future.result()

        if not goal_handle.accepted:
            self.get_logger().error("Goal rejected by aic_model.")
            return

        self.get_logger().info("Goal accepted. Policy is running...")
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        result = result_future.result().result
        self.get_logger().info(
            f"Policy finished. success={result.success}, message='{result.message}'"
        )

    def _feedback_cb(self, feedback_msg):
        self.get_logger().info(f"[feedback] {feedback_msg.feedback.message}")


def main():
    rclpy.init()
    node = PolicyTrigger()
    try:
        node.run()
    except Exception as e:
        node.get_logger().error(f"Error: {e}")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
