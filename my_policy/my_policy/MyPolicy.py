from aic_model.policy import (
    GetObservationCallback,
    MoveRobotCallback,
    Policy,
    SendFeedbackCallback,
)
from aic_task_interfaces.msg import Task
from geometry_msgs.msg import Point, Pose, Quaternion


class MyPolicy(Policy):
    def __init__(self, parent_node):
        super().__init__(parent_node)

    def insert_cable(
        self,
        task: Task,
        get_observation: GetObservationCallback,
        move_robot: MoveRobotCallback,
        send_feedback: SendFeedbackCallback,
    ) -> bool:
        self.get_logger().info(f"MyPolicy.insert_cable() 시작: {task.id}")
        self.get_logger().info(
            f"  케이블: {task.cable_name}/{task.plug_name}"
            f" → 포트: {task.target_module_name}/{task.port_name}"
        )

        send_feedback("MyPolicy 시작")

        # 예시: 현재 위치에서 살짝 위로 이동
        target_pose = Pose(
            position=Point(x=0.3, y=0.0, z=0.5),
            orientation=Quaternion(w=1.0, x=0.0, y=0.0, z=0.0),
        )
        self.set_pose_target(move_robot=move_robot, pose=target_pose)
        self.sleep_for(2.0)

        # 여기에 실제 삽입 로직 구현
        # observation = get_observation()  # 카메라/관절각/힘 데이터
        # ...

        send_feedback("MyPolicy 완료")
        self.get_logger().info("MyPolicy.insert_cable() 종료")
        return False  # 구현 완료 시 True로 변경
