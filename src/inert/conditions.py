from inert.config import Config


def condition_text(
    config: Config,
    condition: str,
    fn: str,
    true_pass: bool,
    channel: str,
    natural: str = "",
    thought: str = "",
) -> str:
    if channel not in config["channels"]:
        raise ValueError(f"Unknown channel: {channel}")
    if condition == "T0":
        return ""
    if condition == "NAT":
        text = (natural if channel == "C" else thought) if natural else ""
    else:
        key = "MIS_OUTCOME" if condition == "CLAIM_POS" else condition
        polarity = "pass" if true_pass and condition != "CLAIM_POS" else "fail"
        text = config["templates"][key][polarity].format(fn=fn)
    return text + config["thought_suffix"] if text and channel == "D" else text
