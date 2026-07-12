#!/usr/bin/env python
"""Fix test file issues."""

with open("tests/test_api_features.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "success_response.json.return_value = mock_response_base" in line:
        lines[i] = '    success_response.json.return_value = {"ok": True, "data": mock_response_base["data"]}\n'
        print(f"Fixed line {i}: success_response")
    if "mock_session.request.return_value = error_response" in line:
        lines[i] = "    mock_session.post.return_value = error_response\n"
        print(f"Fixed line {i}: mock_session.post")

with open("tests/test_api_features.py", "w") as f:
    f.writelines(lines)
print("Done")
