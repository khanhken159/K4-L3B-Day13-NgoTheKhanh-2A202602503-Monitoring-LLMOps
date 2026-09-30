# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

## 1. Thông tin học viên

- **Họ và tên:** Ngô Thế Khanh
- **MSSV:** 2A202602503
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/khanhken159/K4-L3B-Day13-NgoTheKhanh-2A202602503-Monitoring-LLMOps
- **Commit SHA cuối:** Chưa có. `61a34f827748393ced851ea7c9b412dd53dced23` là `HEAD` hiện tại, nhưng working tree còn 33 thay đổi chưa commit nên không được dùng làm SHA nộp cuối.
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602503`

## 2. Evidence index

Các đường dẫn evidence bên dưới là đường dẫn tương đối từ thư mục `submission/`.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | [01-pytest.png](evidence/01-pytest.png) |
| Log validator | [02-log-validator.png](evidence/02-log-validator.png) — 102 records; thiếu trường/context 0; PII 0; điểm ước tính 100/100. |
| Dashboard validator | [03-dashboard-validator.png](evidence/03-dashboard-validator.png) |
| Structured log | [04-structured-log-request.png](evidence/04-structured-log-request.png), [04-structured-log-response.png](evidence/04-structured-log-response.png) |
| PII redaction | [05-pii-redaction.png](evidence/05-pii-redaction.png) |
| Trace list | [06-trace-list.png](evidence/06-trace-list.png) |
| Trace waterfall | [07-trace-waterfall.png](evidence/07-trace-waterfall.png) |
| Trace metadata | [08-trace-metadata.png](evidence/08-trace-metadata.png) cho thấy `correlation_id=req-6a2b8c41`, prompt `day13-chat`, version 1, label `production`; [08-trace-usage.png](evidence/08-trace-usage.png) cho thấy trace `b6d0c159a6af87cf7770d2a427ee1dcb`, 148 tokens và $0.001884. Hai ảnh là hai trace khác nhau nên chưa chứng minh đủ trường trên cùng trace; học viên chọn không chụp lại mục này. |
| Prompt versions | [09-prompt-versions.png](evidence/09-prompt-versions.png), [09-prompt-v2-candidate.png](evidence/09-prompt-v2-candidate.png) |
| Prompt rollback | [10-prompt-promoted.png](evidence/10-prompt-promoted.png), [10-prompt-rollback.png](evidence/10-prompt-rollback.png) |
| Dashboard runtime | [11-dashboard-overview.png](evidence/11-dashboard-overview.png) |
| Incident metric | [12-incident-metric.png](evidence/12-incident-metric.png) |
| Incident log | [13-incident-log.png](evidence/13-incident-log.png) |
| Incident trace | [14-incident-trace.png](evidence/14-incident-trace.png) |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| [`validate_logs.py`](../scripts/validate_logs.py) | Chưa lưu baseline riêng | 100/100; 102 records; thiếu trường/context 0; PII 0 | 50 correlation IDs duy nhất |
| [`validate_dashboard.py`](../scripts/validate_dashboard.py) | Chưa lưu baseline riêng | Hợp lệ 6/6 panel | Đã chạy validator |
| `pytest` | Chưa lưu baseline riêng | 22 passed | Lần chạy trên working tree hiện tại: 1.80 giây |
| Số traces hợp lệ | — | Ít nhất 10 traces gốc | Ảnh trace list trong project cá nhân hiển thị 10 root observations |
| Số PII leak | Chưa lưu baseline riêng | 0 | Validator quét 102 records |
| Latency P95 / TTFT P95 | — | Thường: 724 / 50 ms; challenge: 2,652 / 50 ms | Số liệu từ ảnh dashboard tương ứng |
| Retrieval success rate | — | 100% | Số liệu trên dashboard runtime và challenge |

## 4. Logging và PII

- Middleware nhận `x-request-id` theo định dạng `req-` cộng 8 ký tự hex; nếu header không hợp lệ, ứng dụng tạo ID mới. ID được bind vào request context, trả lại trong response header và dùng xuyên suốt log/trace.
- Structured log ghi timestamp UTC, level, service, event, correlation ID, user ID dạng hash, session ID, feature, model và environment. Log phản hồi còn ghi latency, TTFT, token, cost, quality score và retrieval status.
- Structlog chạy bộ lọc PII trước khi ghi JSONL. Bộ lọc che email, số điện thoại Việt Nam, CCCD, số thẻ, hộ chiếu và địa chỉ; message/answer chỉ lưu bản preview đã scrub.
- `validate_logs.py` hiện báo 102 records, không thiếu trường/context và không phát hiện PII; điểm ước tính 100/100. Ảnh PII dùng dữ liệu giả và cho thấy giá trị đã được che.
- Nguồn kiểm chứng: [`app/middleware.py`](../app/middleware.py), [`app/logging_config.py`](../app/logging_config.py), [`app/pii.py`](../app/pii.py) và [`scripts/validate_logs.py`](../scripts/validate_logs.py).

## 5. Tracing và prompt versioning

- Traces được tạo bởi workload của repository trong project cá nhân `day13-k4-l3b-2A202602503`; ảnh trace list hiển thị project và 10 root observations.
- Mỗi request có root `lab-agent-run` và hai child observations `retrieve-context` (retriever) và `fake-llm-generate` (generation).
- `correlation_id` được thêm vào trace metadata và có cùng giá trị trong structured log; dùng ID này để tìm trace tương ứng.
- **Prompt name:** `day13-chat`; có ba biến `feature`, `docs`, `message`.
- **Baseline cuối:** v1, nhãn `baseline` và `production`.
- **Candidate cuối:** v2, nhãn `candidate` và `latest`.
- **Trace ID của hai version:** Chưa ghi nhận được trong evidence hiện có; đề yêu cầu bổ sung hai ID này vào report.
- Ảnh metadata mục 08 xác nhận correlation ID `req-6a2b8c41` dùng prompt v1 (`day13-chat`, version 1, label `production`); đây là correlation ID, không phải Langfuse trace ID. Ảnh usage có Langfuse trace ID `b6d0c159a6af87cf7770d2a427ee1dcb`, nhưng không chứng minh trace đó thuộc v1 hay v2. Chưa tìm thấy trace ID cho v1 và v2 để đối chiếu rollback.
- Đã promote v2 lên `production`, sau đó rollback `production` về v1. Trace sau rollback có metadata `prompt_version=1`, `prompt_label=production`.
- Nguồn kiểm chứng phần tracing: [`app/agent.py`](../app/agent.py) và [hướng dẫn prompt versioning](../docs/PROMPT_VERSIONING.md).

## 6. Dashboard, SLO và alerts

- Dashboard runtime có sáu panel: latency percentiles/TTFT, request traffic, error rate/retrieval success, cost, token usage và quality proxy. Ảnh thể hiện time range 60 phút, đơn vị và threshold.
- SLO chính là 99.5% request thành công trong cửa sổ 28 ngày; request tốt có `response_sent` và latency không quá 3000 ms. Ngưỡng này dùng để theo dõi latency và lỗi ở cấp dịch vụ.
- Error budget là 0.5%; với 10,000 requests, tối đa 50 requests không đạt SLO.
- Có ba alert, mỗi alert duy trì 5 phút và gửi tới `#k4-l3b-alerts`: `HighLatencyP95`, `HighRequestErrorRate`, `LowRetrievalSuccess`. Runbook nằm trong [`docs/alerts.md`](../docs/alerts.md).
- Cấu hình được lưu tại [`config/slo.yaml`](../config/slo.yaml) và [`config/alert_rules.yaml`](../config/alert_rules.yaml).

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (cohort K4).
- **Khoảng thời gian điều tra:** khoảng 30/09/2026 15:11–15:12, giờ Việt Nam.
- **Triệu chứng từ metrics:** P95 latency 2,652 ms và TTFT P95 50 ms; retrieval success 100%. Dashboard tổng quát đặt SLO latency 3,000 ms nên panel vẫn ghi trong ngưỡng.
- **Log line và correlation ID liên quan:** `response_sent`, `correlation_id=req-593e2d95`, `latency_ms=2651`, feature `monitoring`.
- **Trace ID và span gây ảnh hưởng:** trace `a26a0e2f93a41344812a6a8582485fa0`; span `retrieve-context` mất 2.50 giây, toàn trace khoảng 2.65 giây.
- **Root cause:** challenge bật incident `rag_slow`; hàm retrieval chờ thêm 2.5 giây trước khi trả tài liệu.
- **Fix action:** cần chạy `python scripts/inject_incident.py --disable` khi API hoạt động và xác nhận `/health` báo `rag_slow: false`. Trong lần rà soát này, `/health` tại `127.0.0.1:8000` timeout; source khởi tạo incidents ở `false` khi tiến trình mới chạy nhưng điều đó không xác nhận incident đã được tắt trong runtime sau challenge.
- **Preventive measure:** bổ sung theo dõi thời lượng riêng cho retrieval và kiểm tra alert/runbook cho latency retrieval; ngưỡng hiện tại 3000 ms không báo vượt ngưỡng với P95 2652 ms trong ảnh.
- Nguồn kiểm chứng root cause: [`app/mock_rag.py`](../app/mock_rag.py), [`app/incidents.py`](../app/incidents.py) và [`scripts/inject_incident.py`](../scripts/inject_incident.py).

## 8. Giải thích và tự đánh giá

- **Quyết định kỹ thuật:** chỉ giữ request ID đầu vào đúng định dạng; nếu không, tạo ID mới. Điều này giúp correlation ổn định mà không đưa chuỗi tùy ý vào log.
- **Lỗi/blocker:** khi khởi động lại Uvicorn với `--reload`, Windows báo `PermissionError: [WinError 10013]` tại `socket.socketpair`.
- **Cách xử lý:** tiếp tục tra trace đã được lưu trên Langfuse để hoàn tất điều tra mà không cần server cục bộ; việc khắc phục lỗi khởi động lại server chưa được xác nhận.
- **Metrics → Logs → Traces:** metric chỉ thời điểm latency tăng; correlation ID tìm request cụ thể trong JSONL; cùng ID dẫn tới trace và span `retrieve-context` gây chậm.
- **Chi tiết đọc được từ evidence Langfuse mục 08:** ảnh metadata hiển thị `correlation_id=req-6a2b8c41`, prompt `day13-chat`, version 1, label `production` và model `claude-sonnet-4-5`. Ảnh usage khác hiển thị trace `b6d0c159a6af87cf7770d2a427ee1dcb`, 148 tokens và cost `$0.001884`. Đây là hai trace riêng; report không gán token/cost của trace thứ hai cho request `req-6a2b8c41`.
- Prompt version cho phép rollback cấu hình đã thử; token/cost giúp theo dõi mức sử dụng; SLO đặt ngưỡng dịch vụ và error budget định lượng mức lỗi cho phép.
- **Điều học được:** cần nối metric, log và trace bằng cùng một request ID trước khi kết luận nguyên nhân.
- **Phần còn thiếu trước khi nộp:** xác nhận việc tắt incident; tra hai trace ID prompt v1/v2; commit các thay đổi rồi cập nhật SHA cuối. Ảnh metadata mục 08 được giữ lại với các giá trị đọc được, nhưng chưa đủ trường trên cùng trace; học viên chọn không chụp lại mục này dù checklist yêu cầu.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối; chưa có commit cuối.
- [x] Evidence 02 là ảnh validator cuối: 102 records và 100/100.
- [x] Incident evidence nối metric → log → trace bằng `req-593e2d95`.
- [ ] Evidence metadata mục 08: các trường đọc được đã ghi tại mục 8, nhưng hai ảnh là hai trace khác nhau nên chưa đáp ứng yêu cầu cùng một trace; học viên chọn không chụp lại.
- [x] Trace/prompt evidence hiện có thuộc project Langfuse cá nhân; không thấy API key trong ảnh đã kiểm tra.
- [x] Trên working tree hiện tại: pytest 22 passed; log validator 100/100; dashboard validator 6/6. Chạy lại sau commit cuối vẫn cần thiết.
- [ ] Bổ sung trace ID của hai version prompt vào report.
- [ ] Commit SHA cuối đã được nộp trên LMS/Codelabs.
