"""把短期 ByteTrack track_id 归并为稳定的全局 person_id。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence

import numpy as np

from tracking.appearance_features import appearance_similarity, extract_appearance_feature
from tracking.reid_extractor import ReIDExtractor


@dataclass
class IdentityProfile:
    person_id: int
    appearances: list[np.ndarray]
    last_bbox: list[float]
    last_seen: float
    last_confidence: float


class IdentityManager:
    """使用外观、位置和框尺寸维持动态数量的全局人物身份。"""

    def __init__(
        self,
        max_persons: int = 0,
        appearance_weight: float = 0.75,
        position_weight: float = 0.2,
        size_weight: float = 0.05,
        appearance_match_threshold: float = 0.62,
        position_time_window: float = 1.0,
        template_update_alpha: float = 0.05,
        template_update_min_confidence: float = 0.45,
        confirmation_frames: int = 5,
        pending_ttl_seconds: float = 2.0,
        reid_model_path: str | None = None,
        reid_input_width: int = 128,
        reid_input_height: int = 256,
        reid_use_cuda: bool = True,
        max_appearance_templates: int = 8,
        reid_update_interval: int = 15,
        appearance_match_margin: float = 0.04,
        min_pending_features: int = 3,
        reid_feature_weight: float = 0.65,
        global_merge_threshold: float = 0.42,
    ) -> None:
        # 0 表示不限制人数; 正数可用于已知人数的特定场景。
        self.max_persons = max(0, int(max_persons))
        self.appearance_weight = float(appearance_weight)
        self.position_weight = float(position_weight)
        self.size_weight = float(size_weight)
        self.appearance_match_threshold = float(appearance_match_threshold)
        self.position_time_window = max(0.0, float(position_time_window))
        self.template_update_alpha = min(1.0, max(0.0, float(template_update_alpha)))
        self.template_update_min_confidence = float(template_update_min_confidence)
        self.confirmation_frames = max(1, int(confirmation_frames))
        self.pending_ttl_seconds = max(0.0, float(pending_ttl_seconds))
        self.max_appearance_templates = max(1, int(max_appearance_templates))
        self.reid_update_interval = max(1, int(reid_update_interval))
        self.appearance_match_margin = max(0.0, float(appearance_match_margin))
        self.min_pending_features = max(1, int(min_pending_features))
        self.reid_feature_weight = min(1.0, max(0.0, float(reid_feature_weight)))
        self.global_merge_threshold = float(global_merge_threshold)
        self.reid_extractor = ReIDExtractor(
            model_path=reid_model_path,
            input_width=reid_input_width,
            input_height=reid_input_height,
            use_cuda=reid_use_cuda,
        )

        self._profiles: Dict[int, IdentityProfile] = {}
        self._track_to_person: Dict[int, int] = {}
        self._pending_features: Dict[int, list[np.ndarray]] = {}
        self._pending_counts: Dict[int, int] = {}
        self._pending_last_seen: Dict[int, float] = {}
        self._next_person_id = 1
        self._track_frame_counts: Dict[int, int] = {}
        self._identity_conflicts: set[tuple[int, int]] = set()

    def update(
        self,
        frame: Any,
        tracks: Sequence[Any],
        timestamp: float,
    ) -> list[Any]:
        """为当前帧轨迹分配稳定 person_id。"""
        self._cleanup_pending(timestamp)
        if not tracks:
            return []

        candidates = []
        for track in tracks:
            track_id = int(track.track_id)
            count = self._track_frame_counts.get(track_id, 0) + 1
            self._track_frame_counts[track_id] = count
            known_track = track_id in self._track_to_person
            should_extract_reid = not known_track or count % self.reid_update_interval == 0
            appearance = None
            if self.reid_extractor.available and should_extract_reid:
                reid_feature = self.reid_extractor.extract(frame, track.bbox)
                color_feature = extract_appearance_feature(frame, track.bbox)
                appearance = self._combine_features(reid_feature, color_feature)
            elif not self.reid_extractor.available:
                appearance = extract_appearance_feature(frame, track.bbox)
            candidates.append(
                {
                    "track": track,
                    "track_id": track_id,
                    "bbox": [float(value) for value in track.bbox],
                    "confidence": float(track.confidence),
                    "appearance": appearance,
                }
            )

        assigned_person_ids: set[int] = set()
        pending = []
        assigned_tracks = []

        for candidate in candidates:
            person_id = self._track_to_person.get(candidate["track_id"])
            if person_id is None or person_id in assigned_person_ids:
                pending.append(candidate)
                continue
            identity_confidence = self._identity_score(
                candidate,
                self._profiles[person_id],
                timestamp,
            )
            if candidate["appearance"] is None:
                identity_confidence = self._profiles[person_id].last_confidence
            self._apply_assignment(candidate, person_id, timestamp, identity_confidence)
            assigned_person_ids.add(person_id)
            assigned_tracks.append(candidate["track"])

        pending.sort(key=lambda item: item["confidence"], reverse=True)
        for candidate in pending:
            if not self._confirm_candidate(candidate, timestamp):
                continue
            person_id, identity_confidence = self._match_identity(
                candidate,
                timestamp,
                assigned_person_ids,
            )
            self._track_to_person[candidate["track_id"]] = person_id
            self._apply_assignment(candidate, person_id, timestamp, identity_confidence)
            assigned_person_ids.add(person_id)
            assigned_tracks.append(candidate["track"])
            self._clear_pending(candidate["track_id"])

        active_ids = sorted(assigned_person_ids)
        for index, first_id in enumerate(active_ids):
            for second_id in active_ids[index + 1 :]:
                self._identity_conflicts.add((first_id, second_id))

        return assigned_tracks

    def build_global_identity_map(self) -> Dict[int, int]:
        """基于全视频模板归并碎片身份，同时保留同帧共现人物。"""
        parent = {person_id: person_id for person_id in self._profiles}

        def find(person_id: int) -> int:
            while parent[person_id] != person_id:
                parent[person_id] = parent[parent[person_id]]
                person_id = parent[person_id]
            return person_id

        def cluster_members(root: int) -> set[int]:
            return {person_id for person_id in parent if find(person_id) == root}

        pairs = []
        person_ids = sorted(self._profiles)
        for index, first_id in enumerate(person_ids):
            for second_id in person_ids[index + 1 :]:
                similarity = self._profile_pair_similarity(
                    self._profiles[first_id], self._profiles[second_id]
                )
                if similarity >= self.global_merge_threshold:
                    pairs.append((similarity, first_id, second_id))

        for _, first_id, second_id in sorted(pairs, reverse=True):
            first_root, second_root = find(first_id), find(second_id)
            if first_root == second_root:
                continue
            first_members = cluster_members(first_root)
            second_members = cluster_members(second_root)
            if any(
                tuple(sorted((left, right))) in self._identity_conflicts
                for left in first_members for right in second_members
            ):
                continue
            parent[max(first_root, second_root)] = min(first_root, second_root)

        roots = sorted({find(person_id) for person_id in person_ids})
        normalized = {root: index + 1 for index, root in enumerate(roots)}
        return {person_id: normalized[find(person_id)] for person_id in person_ids}

    @staticmethod
    def _profile_pair_similarity(first: IdentityProfile, second: IdentityProfile) -> float:
        scores = [
            appearance_similarity(left, right)
            for left in first.appearances for right in second.appearances
        ]
        if not scores:
            return 0.0
        scores.sort(reverse=True)
        return float(np.mean(scores[: min(3, len(scores))]))

    def _match_identity(
        self,
        candidate: Dict[str, Any],
        timestamp: float,
        assigned_person_ids: set[int],
    ) -> tuple[int, float]:
        available = [
            profile
            for person_id, profile in self._profiles.items()
            if person_id not in assigned_person_ids
        ]

        scored = [
            (self._identity_score(candidate, profile, timestamp), profile.person_id)
            for profile in available
        ]
        scored.sort(reverse=True)

        if scored:
            best_score, best_person_id = scored[0]
            best_profile = self._profiles[best_person_id]
            appearance_score = self._profile_appearance_similarity(
                candidate["appearance"], best_profile
            )
            second_appearance_score = 0.0
            if len(scored) > 1:
                second_profile = self._profiles[scored[1][1]]
                second_appearance_score = self._profile_appearance_similarity(
                    candidate["appearance"], second_profile
                )
            is_distinct_match = (
                len(scored) == 1
                or appearance_score - second_appearance_score
                >= self.appearance_match_margin
            )
            if (
                appearance_score >= self.appearance_match_threshold
                and is_distinct_match
            ):
                return best_person_id, best_score

        if self._can_create_identity():
            person_id = self._next_person_id
            self._next_person_id += 1
            return person_id, 1.0

        # 所有身份都已被当前帧占用时, 使用外观最接近的身份, 但不创建新 ID。
        all_scored = [
            (self._identity_score(candidate, profile, timestamp), profile.person_id)
            for profile in self._profiles.values()
        ]
        best_score, best_person_id = max(all_scored)
        return best_person_id, best_score

    def _can_create_identity(self) -> bool:
        return self.max_persons == 0 or len(self._profiles) < self.max_persons

    def _confirm_candidate(self, candidate: Dict[str, Any], timestamp: float) -> bool:
        """新轨迹连续存在若干帧后才允许创建全局身份。"""
        track_id = candidate["track_id"]
        self._pending_counts[track_id] = self._pending_counts.get(track_id, 0) + 1
        self._pending_last_seen[track_id] = float(timestamp)

        appearance = candidate["appearance"]
        if appearance is not None:
            self._pending_features.setdefault(track_id, []).append(appearance)

        features = self._pending_features.get(track_id, [])
        if (
            self._pending_counts[track_id] < self.confirmation_frames
            or len(features) < self.min_pending_features
        ):
            return False

        if features:
            stacked = np.stack(features, axis=0)
            center = np.median(stacked, axis=0)
            similarities = stacked @ center
            keep_count = max(1, int(np.ceil(len(features) * 0.7)))
            retained = stacked[np.argsort(similarities)[-keep_count:]]
            averaged = np.mean(retained, axis=0)
            norm = float(np.linalg.norm(averaged))
            candidate["appearance"] = averaged / norm if norm > 1e-6 else appearance
        return True

    def _cleanup_pending(self, timestamp: float) -> None:
        expired = [
            track_id
            for track_id, last_seen in self._pending_last_seen.items()
            if timestamp - last_seen > self.pending_ttl_seconds
        ]
        for track_id in expired:
            self._clear_pending(track_id)

    def _clear_pending(self, track_id: int) -> None:
        self._pending_features.pop(track_id, None)
        self._pending_counts.pop(track_id, None)
        self._pending_last_seen.pop(track_id, None)

    def _identity_score(
        self,
        candidate: Dict[str, Any],
        profile: IdentityProfile,
        timestamp: float,
    ) -> float:
        appearance_score = self._profile_appearance_similarity(
            candidate["appearance"], profile
        )
        size_score = _size_similarity(candidate["bbox"], profile.last_bbox)

        if timestamp - profile.last_seen <= self.position_time_window:
            position_score = _position_similarity(candidate["bbox"], profile.last_bbox)
            score = (
                self.appearance_weight * appearance_score
                + self.position_weight * position_score
                + self.size_weight * size_score
            )
        else:
            total = self.appearance_weight + self.size_weight
            score = (
                self.appearance_weight * appearance_score
                + self.size_weight * size_score
            ) / max(total, 1e-6)

        return max(0.0, min(1.0, score))

    def _apply_assignment(
        self,
        candidate: Dict[str, Any],
        person_id: int,
        timestamp: float,
        identity_confidence: float,
    ) -> None:
        track = candidate["track"]
        track["person_id"] = int(person_id)
        track["identity_confidence"] = round(float(identity_confidence), 4)

        profile = self._profiles.get(person_id)
        if profile is None:
            self._profiles[person_id] = IdentityProfile(
                person_id=person_id,
                appearances=(
                    [candidate["appearance"]]
                    if candidate["appearance"] is not None
                    else []
                ),
                last_bbox=candidate["bbox"],
                last_seen=float(timestamp),
                last_confidence=float(identity_confidence),
            )
            return

        if (
            candidate["appearance"] is not None
            and candidate["confidence"] >= self.template_update_min_confidence
        ):
            self._update_appearance_templates(profile, candidate["appearance"])

        profile.last_bbox = candidate["bbox"]
        profile.last_seen = float(timestamp)
        profile.last_confidence = float(identity_confidence)

    def _combine_features(
        self,
        reid_feature: np.ndarray | None,
        color_feature: np.ndarray | None,
    ) -> np.ndarray | None:
        if reid_feature is None or color_feature is None:
            return None
        reid_weight = self.reid_feature_weight
        color_weight = 1.0 - reid_weight
        combined = np.concatenate(
            (
                np.sqrt(reid_weight) * reid_feature,
                np.sqrt(color_weight) * color_feature,
            )
        ).astype(np.float32)
        norm = float(np.linalg.norm(combined))
        return combined / norm if norm > 1e-6 else None

    def _profile_appearance_similarity(
        self,
        appearance: np.ndarray | None,
        profile: IdentityProfile,
    ) -> float:
        if appearance is None or not profile.appearances:
            return 0.0
        scores = sorted(
            (
                appearance_similarity(appearance, template)
                for template in profile.appearances
            ),
            reverse=True,
        )
        top_scores = scores[: min(3, len(scores))]
        return float(np.mean(top_scores))

    def _update_appearance_templates(
        self,
        profile: IdentityProfile,
        appearance: np.ndarray,
    ) -> None:
        if not profile.appearances:
            profile.appearances.append(appearance)
            return

        similarities = [
            appearance_similarity(appearance, template)
            for template in profile.appearances
        ]
        closest_index = int(np.argmax(similarities))
        if similarities[closest_index] >= 0.9:
            alpha = self.template_update_alpha
            updated = (
                (1.0 - alpha) * profile.appearances[closest_index]
                + alpha * appearance
            )
            norm = float(np.linalg.norm(updated))
            if norm > 1e-6:
                profile.appearances[closest_index] = updated / norm
            return

        profile.appearances.append(appearance)
        if len(profile.appearances) > self.max_appearance_templates:
            profile.appearances.pop(0)


def _position_similarity(first: Sequence[float], second: Sequence[float]) -> float:
    first_center = ((first[0] + first[2]) / 2.0, (first[1] + first[3]) / 2.0)
    second_center = ((second[0] + second[2]) / 2.0, (second[1] + second[3]) / 2.0)
    scale = max(
        first[2] - first[0],
        first[3] - first[1],
        second[2] - second[0],
        second[3] - second[1],
        1.0,
    )
    distance = float(np.hypot(first_center[0] - second_center[0], first_center[1] - second_center[1]))
    return max(0.0, 1.0 - distance / (scale * 2.0))


def _size_similarity(first: Sequence[float], second: Sequence[float]) -> float:
    first_area = max(1.0, (first[2] - first[0]) * (first[3] - first[1]))
    second_area = max(1.0, (second[2] - second[0]) * (second[3] - second[1]))
    return min(first_area, second_area) / max(first_area, second_area)
