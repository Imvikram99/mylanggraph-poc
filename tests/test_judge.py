from src.eval.judge import LLMJudge


def test_judge_scores():
    judge = LLMJudge(model_name="fake")
    verdict = judge.score("prompt", "response with requirements", "requirements")
    assert verdict["verdict"] in {"ACCEPT", "REVIEW"}
