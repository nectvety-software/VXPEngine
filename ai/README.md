# VXPEngine for AI Agents

- Agent hỗ trợ Skills: dùng thư mục `skills/vxpengine-agent/` như một skill cục
  bộ và gọi `$vxpengine-agent` trong yêu cầu.
- Agent không hỗ trợ Skills: đưa toàn bộ `skills/vxpengine-agent/PROMPT.md` vào
  system/developer prompt, rồi cung cấp repository VXPEngine làm workspace.
- Khi chỉ phân phối tài liệu, giữ nguyên cả thư mục `references/`; `SKILL.md` định
  tuyến theo nhiệm vụ và chỉ yêu cầu agent đọc reference cần thiết.

Không đưa khóa ký hoặc nội dung `signing/apps/` vào context gửi cho dịch vụ AI.
