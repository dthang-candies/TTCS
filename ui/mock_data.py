"""
ui/mock_data.py — Dữ liệu giả cho DEMO_MODE
"""

MOCK_INGEST = {
    "session_id":   "demo_001",
    "chunks_a":     22,
    "chunks_b":     25,
    "total_chunks": 47,
    "file_a_name":  "hop_dong_v1.docx",
    "file_b_name":  "hop_dong_v2.docx",
    "message":      "Ingestion thành công (DEMO MODE)",
}

MOCK_CHANGES = [
    {
        "change_type": "SỬA",
        "mo_ta":       "Thời hạn hợp đồng tăng từ 12 tháng lên 24 tháng",
        "vi_tri":      "Điều 2 > Khoản 2.1",
        "muc_do":      "cao",
        "citation_a": {
            "source": "A", "chunk_index": 3,
            "heading_path": "Điều 2 > Khoản 2.1",
            "text": "Thời hạn hợp đồng là 12 (mười hai) tháng kể từ ngày ký kết.",
        },
        "citation_b": {
            "source": "B", "chunk_index": 3,
            "heading_path": "Điều 2 > Khoản 2.1",
            "text": "Thời hạn hợp đồng là 24 (hai mươi bốn) tháng kể từ ngày ký kết.",
        },
        "ly_giai": "Tăng gấp đôi thời hạn ảnh hưởng đến cam kết dài hạn của các bên.",
    },
    {
        "change_type": "SỬA",
        "mo_ta":       "Giá trị hợp đồng tăng 15% (từ 500 triệu lên 575 triệu)",
        "vi_tri":      "Điều 4 > Khoản 4.2",
        "muc_do":      "cao",
        "citation_a": {
            "source": "A", "chunk_index": 8,
            "heading_path": "Điều 4 > Khoản 4.2",
            "text": "Tổng giá trị hợp đồng là 500.000.000 đồng (Năm trăm triệu đồng).",
        },
        "citation_b": {
            "source": "B", "chunk_index": 8,
            "heading_path": "Điều 4 > Khoản 4.2",
            "text": "Tổng giá trị hợp đồng là 575.000.000 đồng (Năm trăm bảy mươi lăm triệu đồng).",
        },
        "ly_giai": None,
    },
    {
        "change_type": "THÊM",
        "mo_ta":       "Bổ sung điều khoản phạt vi phạm tiến độ (0.05%/ngày)",
        "vi_tri":      "Điều 7 > Khoản 7.4",
        "muc_do":      "cao",
        "citation_a":  None,
        "citation_b": {
            "source": "B", "chunk_index": 15,
            "heading_path": "Điều 7 > Khoản 7.4",
            "text": "Trường hợp Bên B vi phạm tiến độ giao hàng quá 15 ngày, Bên B phải chịu phạt 0,05% giá trị hợp đồng cho mỗi ngày chậm trễ.",
        },
        "ly_giai": "Điều khoản mới hoàn toàn, không tồn tại trong phiên bản gốc.",
    },
    {
        "change_type": "XÓA",
        "mo_ta":       "Xóa điều khoản bất khả kháng liên quan đến dịch bệnh",
        "vi_tri":      "Điều 9 > Khoản 9.3",
        "muc_do":      "trung bình",
        "citation_a": {
            "source": "A", "chunk_index": 19,
            "heading_path": "Điều 9 > Khoản 9.3",
            "text": "Các trường hợp bất khả kháng bao gồm: thiên tai, dịch bệnh, chiến tranh, hoặc quyết định của cơ quan nhà nước có thẩm quyền.",
        },
        "citation_b":  None,
        "ly_giai":     None,
    },
    {
        "change_type": "SỬA",
        "mo_ta":       "Phương thức thanh toán chuyển từ chuyển khoản sang L/C",
        "vi_tri":      "Điều 5 > Khoản 5.1",
        "muc_do":      "cao",
        "citation_a": {
            "source": "A", "chunk_index": 10,
            "heading_path": "Điều 5 > Khoản 5.1",
            "text": "Bên A thanh toán bằng hình thức chuyển khoản ngân hàng trong vòng 30 ngày kể từ ngày nhận hàng.",
        },
        "citation_b": {
            "source": "B", "chunk_index": 10,
            "heading_path": "Điều 5 > Khoản 5.1",
            "text": "Bên A thanh toán bằng thư tín dụng (L/C) không hủy ngang, thanh toán ngay tại ngân hàng thông báo.",
        },
        "ly_giai": "Thay đổi phương thức thanh toán làm tăng rủi ro tài chính cho Bên A.",
    },
    {
        "change_type": "THÊM",
        "mo_ta":       "Bổ sung điều khoản bảo mật thông tin (5 năm sau khi chấm dứt)",
        "vi_tri":      "Điều 11",
        "muc_do":      "trung bình",
        "citation_a":  None,
        "citation_b": {
            "source": "B", "chunk_index": 22,
            "heading_path": "Điều 11",
            "text": "Các bên cam kết bảo mật toàn bộ thông tin liên quan đến hợp đồng này trong thời hạn 05 năm kể từ ngày hợp đồng chấm dứt.",
        },
        "ly_giai": None,
    },
    {
        "change_type": "SỬA",
        "mo_ta":       "Thời gian bảo hành rút ngắn từ 12 tháng xuống 6 tháng",
        "vi_tri":      "Điều 6 > Khoản 6.2",
        "muc_do":      "trung bình",
        "citation_a": {
            "source": "A", "chunk_index": 13,
            "heading_path": "Điều 6 > Khoản 6.2",
            "text": "Bên B bảo hành sản phẩm trong thời gian 12 tháng kể từ ngày nghiệm thu.",
        },
        "citation_b": {
            "source": "B", "chunk_index": 13,
            "heading_path": "Điều 6 > Khoản 6.2",
            "text": "Bên B bảo hành sản phẩm trong thời gian 06 tháng kể từ ngày nghiệm thu.",
        },
        "ly_giai": None,
    },
    {
        "change_type": "KHÔNG ĐỔI NỘI DUNG",
        "mo_ta":       "Điều khoản giải quyết tranh chấp — nội dung giữ nguyên, chỉnh sửa câu chữ",
        "vi_tri":      "Điều 12 > Khoản 12.1",
        "muc_do":      "thấp",
        "citation_a": {
            "source": "A", "chunk_index": 24,
            "heading_path": "Điều 12 > Khoản 12.1",
            "text": "Mọi tranh chấp phát sinh từ hoặc liên quan đến hợp đồng này sẽ được giải quyết bằng thương lượng.",
        },
        "citation_b": {
            "source": "B", "chunk_index": 24,
            "heading_path": "Điều 12 > Khoản 12.1",
            "text": "Các tranh chấp liên quan đến hợp đồng này trước tiên sẽ được các bên giải quyết thông qua thương lượng thiện chí.",
        },
        "ly_giai": "Nội dung không thay đổi, chỉ điều chỉnh cách diễn đạt.",
    },
]

MOCK_COMPARE = {
    "session_id":        "demo_001",
    "total_changes":     len(MOCK_CHANGES),
    "changes_added":     sum(1 for c in MOCK_CHANGES if c["change_type"] == "THÊM"),
    "changes_deleted":   sum(1 for c in MOCK_CHANGES if c["change_type"] == "XÓA"),
    "changes_modified":  sum(1 for c in MOCK_CHANGES if c["change_type"] == "SỬA"),
    "changes_unchanged": sum(1 for c in MOCK_CHANGES if c["change_type"] == "KHÔNG ĐỔI NỘI DUNG"),
    "change_list":       MOCK_CHANGES,
    "tom_tat": (
        "Phiên bản B có 7 thay đổi đáng chú ý so với phiên bản A. "
        "Nổi bật nhất là thời hạn hợp đồng tăng gấp đôi (12 → 24 tháng), "
        "giá trị hợp đồng tăng 15%, và phương thức thanh toán chuyển sang L/C. "
        "Ngoài ra có 2 điều khoản mới (phạt vi phạm tiến độ, bảo mật thông tin) "
        "và 1 điều khoản bất khả kháng bị xóa."
    ),
    "processing_time": 9.4,
}
