import json
import logging

log = logging.getLogger("qwen2api.prompt")

def build_prompt_with_tools(messages: list, tools: list) -> str:
    """
    将标准 messages 列表和 tools 列表转换为一段携带劫持指令的纯文本 Prompt。
    如果存在 tools，将彻底覆盖原有的 System Prompt，植入 ##TOOL_CALL## 强制指令。
    """
    prompt = ""
    system_text = ""
    
    # 提取并合并原始系统提示词
    for m in messages:
        if m.get("role") == "system":
            system_text += str(m.get("content", "")) + "\n"
            
    if tools:
        # 劫持系统提示词
        names = [t.get("function", {}).get("name", "") if "function" in t else t.get("name", "") for t in tools]
        names = [n for n in names if n]
        
        prompt += "=== MANDATORY TOOL CALL INSTRUCTIONS ===\n"
        prompt += "IGNORE any previous output format instructions (needs-review, recap, etc.).\n"
        prompt += f"You have access to these tools: {', '.join(names)}\n\n"
        prompt += "WHEN YOU NEED TO CALL A TOOL — output EXACTLY this format (nothing else):\n"
        prompt += "##TOOL_CALL##\n"
        prompt += '{"name": "EXACT_TOOL_NAME", "input": {"param1": "value1"}}\n'
        prompt += "##END_CALL##\n\n"
        
        prompt += "MULTI-TURN RULES:\n"
        prompt += "- After a [Tool Result] block appears in the conversation, read it and decide next action.\n"
        prompt += "- If more tool calls are needed, emit another ##TOOL_CALL## block.\n"
        prompt += "- Only give a final text answer when ALL needed information is gathered.\n"
        prompt += "- Never skip calling a tool that is required to complete the user request.\n\n"
        
        prompt += "STRICT RULES:\n"
        prompt += "- No preamble, no explanation before or after ##TOOL_CALL##...##END_CALL##.\n"
        prompt += "- Use EXACT tool name from the list below.\n"
        prompt += "- When NO tool is needed, answer normally in plain text.\n\n"
        
        prompt += "CRITICAL — FORBIDDEN FORMATS:\n"
        prompt += "- <tool_call>{...}</tool_call>  <-- NEVER USE\n"
        prompt += "- {\"name\": \"X\", \"arguments\": \"...\"}  <-- NEVER USE\n"
        prompt += "ONLY ##TOOL_CALL##...##END_CALL## is accepted.\n\n"
        prompt += "Available tools:\n"
        prompt += json.dumps(tools, ensure_ascii=False, indent=2) + "\n\n"
        
    elif system_text:
        prompt += f"<system>\n{system_text}</system>\n\n"
        
    # 拼接对话历史
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        
        if role == "system":
            continue
            
        if role == "tool":
            tid = m.get("tool_call_id", "")
            prompt += f"[Tool Result for call {tid}]\n{content}\n[/Tool Result]\n\n"
        elif role == "user":
            prompt += f"User: {content}\n\n"
        elif role == "assistant":
            # 如果助手回复包含 tool_calls，格式化为模型能看懂的伪历史
            tcs = m.get("tool_calls", [])
            if tcs:
                for tc in tcs:
                    fn = tc.get("function", {})
                    inp = fn.get("arguments", "{}")
                    try:
                        inp_obj = json.loads(inp)
                        inp_str = json.dumps(inp_obj, ensure_ascii=False)
                    except:
                        inp_str = inp
                    prompt += f'##TOOL_CALL##\n{{"name": "{fn.get("name", "")}", "input": {inp_str}}}\n##END_CALL##\n'
            if content:
                prompt += f"Assistant: {content}\n\n"
                
    prompt += "Assistant: "
    return prompt
