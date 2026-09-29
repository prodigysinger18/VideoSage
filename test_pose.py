from video_processing.video_reader import VideoReader
from detection.yolo_pose import YOLOPose
import cv2
import os


# =========================
# 配置
# =========================

VIDEO_PATH = r"E:\VideoSage\data\videos"

MODEL_PATH = r"E:\VideoSage\models\yolo\yolo11n-pose.pt"

OUTPUT_PATH = r"E:\VideoSage\data\results\poses\pose_test.jpg"


# =========================
# 1. 创建视频读取器
# =========================

reader = VideoReader(
    video_path=VIDEO_PATH,
    frame_start=0,
    frame_stride=1,
    max_frames=100,
)

print("========== 视频信息 ==========")
print(reader.get_info())


# =========================
# 2. 创建 Pose 模型
# =========================

pose_model = YOLOPose(
    model_path=MODEL_PATH,
    conf_threshold=0.25,
    imgsz=640,
    max_det=10,
    device=0,
    quantize=16,
)

print("\nYOLO11 Pose 模型加载成功")


# =========================
# 3. 读取视频中的一帧
# =========================

target_frame = None
target_timestamp = 0.0

try:
    for frame in reader.read():

        target_frame = frame.copy()
        target_timestamp = reader.current_timestamp

        print(
            f"正在测试第 {reader.current_frame_id} 帧，"
            f"时间 {target_timestamp:.2f} 秒"
        )

        pose_results = pose_model.detect(target_frame)

        if len(pose_results) > 0:

            print(
                f"\n在 {target_timestamp:.2f} 秒检测到 "
                f"{len(pose_results)} 个人"
            )

            for person_index, person in enumerate(pose_results):

                print(
                    f"人物 {person_index + 1}: "
                    f"{len(person['keypoints'])} 个关键点"
                )

            visualized = target_frame.copy()

            for person in pose_results:

                for x, y, confidence in person["keypoints"]:

                    if confidence < 0.3:
                        continue

                    cv2.circle(
                        visualized,
                        (int(x), int(y)),
                        4,
                        (0, 255, 0),
                        -1,
                    )

            os.makedirs(
                os.path.dirname(OUTPUT_PATH),
                exist_ok=True,
            )

            cv2.imwrite(
                OUTPUT_PATH,
                visualized,
            )

            print("\nPose 测试成功！")
            print("结果保存：")
            print(OUTPUT_PATH)

            break

finally:
    reader.release()


if target_frame is None:
    raise RuntimeError("没有成功读取视频帧")


print(f"\n测试帧时间：{target_timestamp:.2f} 秒")


# =========================
# 4. Pose 检测
# =========================

pose_results = pose_model.detect(target_frame)


# =========================
# 5. 输出结果
# =========================

print("\n========== Pose 检测结果 ==========")

print("检测到人物数量：", len(pose_results))

for person_index, person in enumerate(pose_results):

    print(f"\n人物 {person_index + 1}")

    print("bbox：", person["bbox"])

    print(
        "confidence：",
        round(person["confidence"], 3)
    )

    keypoints = person["keypoints"]

    print("关键点数量：", len(keypoints))

    for keypoint_index, keypoint in enumerate(keypoints):

        x, y, confidence = keypoint

        print(
            f"  {keypoint_index:02d}: "
            f"x={x:.1f}, "
            f"y={y:.1f}, "
            f"conf={confidence:.3f}"
        )


# =========================
# 6. 画出关键点
# =========================

visualized = target_frame.copy()

for person in pose_results:

    keypoints = person["keypoints"]

    for x, y, confidence in keypoints:

        if confidence < 0.3:
            continue

        cv2.circle(
            visualized,
            (int(x), int(y)),
            4,
            (0, 255, 0),
            -1,
        )


# =========================
# 7. 保存测试图片
# =========================

os.makedirs(
    os.path.dirname(OUTPUT_PATH),
    exist_ok=True,
)

cv2.imwrite(
    OUTPUT_PATH,
    visualized,
)

print("\n测试结果已保存：")
print(OUTPUT_PATH)