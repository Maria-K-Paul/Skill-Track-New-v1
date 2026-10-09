from __future__ import annotations

from .question_paper_generator.config import CONFIG
from .question_paper_generator.graph.workflow import build_graph


def run_pipeline(input_data: dict):
    graph = build_graph()
    result = graph.invoke({"input_data": input_data})
    if result.get("status") == "FAILED":
        return {
            "status": "FAILED",
            "errors": result.get("errors", [{"type": "GENERATION_FAILURE", "message": "Question generation failed."}]),
            "details": {
                "required": input_data["test"]["total_questions"],
                "valid": len(result.get("accepted_questions", [])),
                "missing": max(input_data["test"]["total_questions"] - len(result.get("accepted_questions", [])), 0),
                "max_regeneration_rounds": CONFIG["MAX_REGENERATION_ROUNDS"],
            },
        }
    return result["final_paper"]


if __name__ == "__main__":
    inputJSON = {
    "test": {
        "name": "Cloud Developer",
        "level": 2,
        "duration_minutes": 90,
        "total_marks": 60,
        "total_questions": 30
    },

    "syllabus": {
        "topics": [
        {
            "name": "Cloud Fundamentals",
            "weightage": 30,
            "subtopics": [
            {
                "name": "Cloud Computing Concepts",
                "weightage": 25
            },
            {
                "name": "Cloud Service Models (IaaS, PaaS, SaaS)",
                "weightage": 15
            },
            {
                "name": "Cloud Deployment Models (Public, Private, Hybrid)",
                "weightage": 15
            },
            {
                "name": "Scalability, Elasticity, Availability and Reliability",
                "weightage": 20
            },
            {
                "name": "Shared Responsibility and Cloud Security Basics",
                "weightage": 15
            },
            {
                "name": "Cloud Economics and Pricing Basics",
                "weightage": 10
            }
            ]
        },

        {
            "name": "AWS",
            "weightage": 35,
            "subtopics": [
            {
                "name": "AWS Global Infrastructure (Regions, Availability Zones, Edge Locations)",
                "weightage": 10
            },
            {
                "name": "AWS Compute (EC2, Lambda)",
                "weightage": 20
            },
            {
                "name": "AWS Storage (S3, EBS)",
                "weightage": 15
            },
            {
                "name": "AWS Networking (VPC, Subnets, Security Groups, Route 53)",
                "weightage": 15
            },
            {
                "name": "AWS Databases (RDS, DynamoDB)",
                "weightage": 10
            },
            {
                "name": "AWS Identity and Security (IAM, MFA, Least Privilege)",
                "weightage": 15
            },
            {
                "name": "AWS Monitoring and Cost Management (CloudWatch, Billing, Pricing)",
                "weightage": 10
            },
            {
                "name": "AWS Access and Developer Tools (Console, CLI, SDK Basics)",
                "weightage": 5
            }
            ]
        },

        {
            "name": "Azure",
            "weightage": 35,
            "subtopics": [
            {
                "name": "Azure Core Architecture (Regions, Availability Zones, Resources, Resource Groups, Subscriptions)",
                "weightage": 15
            },
            {
                "name": "Azure Compute (Virtual Machines, VM Scale Sets, App Service, Azure Functions)",
                "weightage": 20
            },
            {
                "name": "Azure Storage (Blob Storage, Files, Storage Tiers and Redundancy)",
                "weightage": 15
            },
            {
                "name": "Azure Networking (Virtual Network, Subnets, DNS, VPN Gateway)",
                "weightage": 15
            },
            {
                "name": "Azure Identity and Security (Microsoft Entra ID, RBAC, MFA)",
                "weightage": 15
            },
            {
                "name": "Azure Management, Governance and Monitoring (Portal, CLI, Azure Policy, Cost Management, Azure Monitor)",
                "weightage": 20
            }
            ]
        }
        ]
    },

    "difficulty_ratio": {
        "Easy": 40,
        "Medium": 40,
        "Hard": 20
    },

    "bloom_level_ratio": {
        "remember": 5,
        "understand": 5,
        "apply": 5,
        "analyze": 5,
        "evaluate": 5,
        "create": 5
    },

    "question_distribution": {
        "MCQ": 30
    },

    "marks_distribution": {
        "MCQ": 2
    },

    "question_constraints": {
        "minimum_options_for_mcq": 4,
        "allow_multiple_correct_answers": False,
        "negative_marking": False,
        "negative_marks": 0,
        "allow_partial_marking": False
    },

    "output_requirements": {
        "include_answer_key": True,
        "include_explanations": True,
        "include_topic_tags": True,
        "include_difficulty": True,
        "include_marks": True
    }
    }
    
    
    outputJSON = run_pipeline(inputJSON)
    print(outputJSON)
