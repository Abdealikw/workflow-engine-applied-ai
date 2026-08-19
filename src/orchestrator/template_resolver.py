import re
from typing import Any, Dict

def resolve_templates(config: Any, node_outputs: Dict[str, Dict[str, Any]]) -> Any:
    """
    Recursively resolves `{{ node_id.key }}` in the config dictionary using node_outputs.
    """
    if isinstance(config, str):
        # Match `{{ node_id.key }}`
        pattern = r"\{\{\s*([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_-]+)\s*\}\}"
        matches = re.finditer(pattern, config)
        
        result_str = config
        for match in matches:
            full_match = match.group(0)
            node_id = match.group(1)
            key = match.group(2)
            
            if node_id in node_outputs and key in node_outputs[node_id]:
                val = node_outputs[node_id][key]
                if full_match == config:
                    # If the entire string is just the template, return the typed value
                    return val
                else:
                    # Replace in string
                    result_str = result_str.replace(full_match, str(val))
        return result_str
        
    elif isinstance(config, dict):
        return {k: resolve_templates(v, node_outputs) for k, v in config.items()}
    elif isinstance(config, list):
        return [resolve_templates(item, node_outputs) for item in config]
    else:
        return config
