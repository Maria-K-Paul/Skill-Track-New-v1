from __future__ import annotations

from collections import OrderedDict


def validate_question_constraints(constraints: dict) -> bool:
    if constraints.get("minimum_options_for_mcq", 0) < 4:
        return False
    if constraints.get("allow_multiple_correct_answers"):
        return False
    if constraints.get("negative_marking") and constraints.get("negative_marks", 0) > 0:
        return False
    if constraints.get("allow_partial_marking"):
        return False
    return True


def largest_remainder_allocation(total: int, weights: dict[str, int]) -> dict[str, int]:
    if total <= 0:
        return {k: 0 for k in weights}
    raw = {k: total * (v / 100) for k, v in weights.items()}
    allocations = {k: int(value) for k, value in raw.items()}
    remainders = sorted(
        ((raw[k] - allocations[k], k) for k in weights),
        key=lambda item: (-item[0], item[1]),
    )
    remaining = total - sum(allocations.values())
    for _, key in remainders[:remaining]:
        allocations[key] += 1
    return OrderedDict((key, allocations[key]) for key in weights)


def calculate_topic_distribution(total_questions: int, topic_weights: dict[str, int]) -> dict[str, int]:
    return largest_remainder_allocation(total_questions, topic_weights)


def calculate_difficulty_distribution(total_questions: int, ratios: dict[str, int]) -> dict[str, int]:
    return largest_remainder_allocation(total_questions, ratios)


def calculate_subtopic_distribution(topic_total: int, subtopic_weights: dict[str, int]) -> dict[str, int]:
    return largest_remainder_allocation(topic_total, subtopic_weights)


def calculate_bloom_level_distribution(total_questions: int, ratios: dict[str, int]) -> dict[str, int]:
    if sum(ratios.values()) == total_questions:
        return OrderedDict((key, ratios.get(key, 0)) for key in ratios)
    return largest_remainder_allocation(total_questions, ratios)


def build_blueprint(
    test_config,
    difficulty_ratio: dict[str, int],
    bloom_level_ratio: dict[str, int] | None = None,
) -> dict:
    topic_counts = calculate_topic_distribution(test_config.test.total_questions, {
        topic.name: topic.weightage for topic in test_config.syllabus.topics
    })

    difficulty_counts = calculate_difficulty_distribution(test_config.test.total_questions, difficulty_ratio)
    bloom_level_ratio = bloom_level_ratio or {"remember": 100}
    bloom_level_counts = calculate_bloom_level_distribution(
        test_config.test.total_questions,
        bloom_level_ratio,
    )
    difficulty_order = ["Easy", "Medium", "Hard"]
    bloom_level_order = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
    requirements = []
    remaining_difficulty = dict(difficulty_counts)
    remaining_bloom_levels = dict(bloom_level_counts)

    for topic in test_config.syllabus.topics:
        topic_question_count = topic_counts.get(topic.name, 0)
        subtopic_weights = {subtopic.name: subtopic.weightage for subtopic in topic.subtopics}
        subtopic_counts = calculate_subtopic_distribution(topic_question_count, subtopic_weights)

        for subtopic in topic.subtopics:
            count = subtopic_counts.get(subtopic.name, 0)
            for _ in range(count):
                chosen_difficulty = None
                for difficulty_name in difficulty_order:
                    if remaining_difficulty.get(difficulty_name, 0) > 0:
                        chosen_difficulty = difficulty_name
                        remaining_difficulty[difficulty_name] -= 1
                        break
                if chosen_difficulty is None:
                    chosen_difficulty = difficulty_order[0]
                chosen_bloom_level = None
                for bloom_level in bloom_level_order:
                    if remaining_bloom_levels.get(bloom_level, 0) > 0:
                        chosen_bloom_level = bloom_level
                        remaining_bloom_levels[bloom_level] -= 1
                        break
                if chosen_bloom_level is None:
                    chosen_bloom_level = bloom_level_order[0]
                requirements.append({
                    "topic": topic.name,
                    "subtopic": subtopic.name,
                    "difficulty": chosen_difficulty,
                    "bloom_level": chosen_bloom_level,
                    "count": 1,
                })

    if sum(req["count"] for req in requirements) != test_config.test.total_questions:
        diff = test_config.test.total_questions - sum(req["count"] for req in requirements)
        while diff > 0:
            requirements.append({
                "topic": test_config.syllabus.topics[0].name,
                "subtopic": test_config.syllabus.topics[0].subtopics[0].name,
                "difficulty": "Easy",
                "bloom_level": bloom_level_order[0],
                "count": 1,
            })
            diff -= 1

    return {
        "total_questions": test_config.test.total_questions,
        "topic_distribution": topic_counts,
        "difficulty_distribution": difficulty_counts,
        "bloom_level_distribution": bloom_level_counts,
        "requirements": requirements,
    }
