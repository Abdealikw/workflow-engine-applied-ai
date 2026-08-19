from src.orchestrator.template_resolver import resolve_templates

def test_resolve_string_template():
    config = {"url": "http://api.com/user/{{ get_user.id }}"}
    outputs = {
        "get_user": {"id": 123}
    }
    
    resolved = resolve_templates(config, outputs)
    assert resolved["url"] == "http://api.com/user/123"

def test_resolve_entire_value():
    config = {"user_data": "{{ get_user.data }}"}
    outputs = {
        "get_user": {"data": {"name": "Alice", "age": 30}}
    }
    
    resolved = resolve_templates(config, outputs)
    # When the whole string is a template, it should retain its type
    assert resolved["user_data"] == {"name": "Alice", "age": 30}

def test_resolve_nested_dict():
    config = {
        "body": {
            "post_id": "{{ get_post.id }}",
            "comment": "Nice!"
        }
    }
    outputs = {
        "get_post": {"id": 42}
    }
    
    resolved = resolve_templates(config, outputs)
    assert resolved["body"]["post_id"] == 42
