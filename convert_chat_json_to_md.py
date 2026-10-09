#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
微信聊天记录 JSON 转 Markdown 工具
功能：
1. 默认无参运行：自动遍历当前目录下所有 JSON 聊天记录文件并进行批量转换，输出至当前目录。
2. 支持指定目录：可通过 -d / --dir 参数指定待扫描的目录路径。
3. 自动文件命名：输出文件名自动附带原始导出日期（如：邵慧留_聊天记录_导出2026-10-07.md）。
4. 完整元数据头：在 Markdown 开头生成详细的原始信息、会话信息、转换参数以及统计图表。
5. 容错与过滤：自动跳过非聊天记录格式的普通 JSON 文件，遇到异常文件不中断整个批处理流程。
"""

import os
import sys
import json
import glob
import argparse
from datetime import datetime
from collections import Counter
from typing import List, Dict, Any, Tuple, Optional


def format_bytes(size: int) -> str:
    """格式化文件大小为易读形式"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def parse_export_time(export_time_raw: str) -> Tuple[str, str]:
    """解析原始导出时间，返回 (完整格式化时间, 导出日期)"""
    if not export_time_raw:
        return "未知", "未知"
    
    clean_time = export_time_raw.replace("T", " ").split(".")[0]
    date_part = clean_time.split(" ")[0] if " " in clean_time else export_time_raw[:10]
    return clean_time, date_part


def extract_messages(
    messages: List[Dict[str, Any]], 
    include_system: bool = True
) -> List[Dict[str, Any]]:
    """
    提取聊天记录中的时间、发送人和内容
    """
    extracted = []
    for msg in messages:
        msg_type = msg.get("type", "")
        is_send = msg.get("isSend")
        
        # 区分发送者
        if msg_type == "系统消息" or is_send is None:
            if not include_system:
                continue
            sender = "系统消息"
        else:
            sender = msg.get("senderDisplayName") or ("我" if is_send == 1 else "对方")
            
        time_str = msg.get("formattedTime", "")
        content = msg.get("content", "")
        
        if content is None:
            content = ""
            
        extracted.append({
            "time": time_str,
            "sender": sender,
            "content": content,
            "type": msg_type,
            "isSend": is_send
        })
    return extracted


def build_markdown_header(
    input_path: str,
    raw_data: Dict[str, Any],
    extracted_messages: List[Dict[str, Any]],
    style: str,
    include_system: bool,
    group_by_date: bool
) -> str:
    """
    生成详尽的 Markdown 文件头部信息
    """
    session = raw_data.get("session", {}) if isinstance(raw_data, dict) else {}
    export_time_raw = raw_data.get("exportTime", "") if isinstance(raw_data, dict) else ""
    formatted_export_time, _ = parse_export_time(export_time_raw)
    
    file_name = os.path.basename(input_path)
    file_size_str = format_bytes(os.path.getsize(input_path)) if os.path.exists(input_path) else "未知"

    display_name = session.get("displayName") or session.get("remark") or session.get("nickname") or "未知"
    nickname = session.get("nickname", "未知")
    wxid = session.get("wxid", "未知")
    session_type = session.get("type", "私聊")

    times = [m["time"] for m in extracted_messages if m.get("time")]
    if times:
        start_time = times[0]
        end_time = times[-1]
        try:
            t0 = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            t1 = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            span_days = (t1 - t0).days + 1
            span_text = f"{start_time} 至 {end_time} (共 {span_days} 天)"
        except Exception:
            span_text = f"{start_time} 至 {end_time}"
    else:
        span_text = "无有效时间记录"

    sender_counter = Counter(m["sender"] for m in extracted_messages)
    total_count = len(extracted_messages)
    type_counter = Counter(m["type"] for m in extracted_messages)

    style_names = {
        "dialog": "对话块风格 (清晰易读)",
        "list": "列表风格 (紧凑)",
        "table": "表格风格"
    }

    lines = [
        f"# 💬 微信聊天记录导出与整理文档",
        "",
        "> 本文件由 JSON 转换脚本自动生成，完整提取了聊天时间、发言人与消息内容。",
        "",
        "---",
        "",
        "## 📋 原始文件与会话信息",
        f"- **源数据文件**：`{file_name}` ({file_size_str})",
        f"- **数据导出时间**：{formatted_export_time}",
        f"- **会话对象**：**{display_name}** (微信昵称: `{nickname}`, 账号: `{wxid}`)",
        f"- **会话类型**：{session_type}",
        f"- **记录时间跨度**：{span_text}",
        "",
        "## ⚙️ 转换配置与参数",
        f"- **脚本生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **排版渲染风格**：{style_names.get(style, style)}",
        f"- **保留系统消息**：{'是' if include_system else '否 (已过滤)'}",
        f"- **按日期标题分组**：{'是' if group_by_date else '否'}",
        "",
        "## 📊 消息数据概览与统计",
        f"- **提取消息总数**：**{total_count:,}** 条",
        "- **发言人统计分布**："
    ]

    for sender, count in sender_counter.most_common():
        pct = (count / total_count * 100) if total_count > 0 else 0
        lines.append(f"  - **{sender}**：{count:,} 条 ({pct:.1f}%)")

    lines.append("- **消息类型细分**：")
    for mtype, count in type_counter.most_common():
        pct = (count / total_count * 100) if total_count > 0 else 0
        lines.append(f"  - {mtype}：{count:,} 条 ({pct:.1f}%)")

    lines.extend([
        "",
        "---",
        ""
    ])

    return "\n".join(lines)


def format_to_markdown_body(
    extracted: List[Dict[str, Any]], 
    style: str = "dialog", 
    group_by_date: bool = True
) -> str:
    """
    格式化正文为 Markdown 字符串
    """
    lines = []
    current_date = ""

    for item in extracted:
        t = item["time"]
        sender = item["sender"]
        content = item["content"].strip()
        
        date_part = t.split(" ")[0] if " " in t else ""
        if group_by_date and date_part and date_part != current_date:
            current_date = date_part
            lines.append(f"\n## 📅 {current_date}\n")

        if style == "dialog":
            lines.append(f"**[{t}] {sender}：**\n{content}\n")
        elif style == "list":
            if "\n" in content:
                indented = "\n  ".join(content.split("\n"))
                lines.append(f"- **[{t}] {sender}**：\n  {indented}")
            else:
                lines.append(f"- **[{t}] {sender}**：{content}")
        elif style == "table":
            safe_content = content.replace("|", "\\|").replace("\n", "<br>")
            lines.append(f"| {t} | {sender} | {safe_content} |")

    return "\n".join(lines)


def convert_single_json(
    input_path: str,
    output_dir: Optional[str] = None,
    output_path: Optional[str] = None,
    include_system: bool = True,
    style: str = "dialog",
    group_by_date: bool = True
) -> Tuple[bool, str]:
    """
    转换单个 JSON 文件为 Markdown 文件
    返回: (成功状态, 输出路径或跳过/错误原因)
    """
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, f"JSON 文件解析失败 ({e})"

    # 判断是否为聊天记录格式
    messages = data.get("messages", []) if isinstance(data, dict) else (data if isinstance(data, list) else None)
    if not isinstance(messages, list) or len(messages) == 0:
        return False, "跳过：非聊天记录格式或未包含有效消息列表"

    extracted = extract_messages(messages, include_system=include_system)

    # 确定输出文件名与路径
    if not output_path:
        export_time_raw = data.get("exportTime", "") if isinstance(data, dict) else ""
        _, export_date = parse_export_time(export_time_raw)
        
        session = data.get("session", {}) if isinstance(data, dict) else {}
        name = session.get("displayName") or session.get("remark") or session.get("nickname")
        if not name:
            base = os.path.splitext(os.path.basename(input_path))[0]
            name = base.split("_")[0]

        if export_date and export_date != "未知":
            md_filename = f"{name}_聊天记录_导出{export_date}.md"
        else:
            md_filename = f"{name}_聊天记录.md"

        target_dir = output_dir if output_dir else os.path.dirname(input_path)
        if not target_dir:
            target_dir = "."
        output_path = os.path.join(target_dir, md_filename)

    # 生成 Markdown 头部与正文
    header = build_markdown_header(
        input_path=input_path,
        raw_data=data,
        extracted_messages=extracted,
        style=style,
        include_system=include_system,
        group_by_date=group_by_date
    )

    if style == "table":
        table_header = "| 时间 | 发送人 | 消息内容 |\n| :--- | :--- | :--- |\n"
        body = format_to_markdown_body(extracted, style=style, group_by_date=False)
        full_content = header + table_header + body
    else:
        body = format_to_markdown_body(extracted, style=style, group_by_date=group_by_date)
        full_content = header + body

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_content)

    return True, output_path


def process_directory(
    target_dir: str,
    output_dir: Optional[str] = None,
    recursive: bool = False,
    include_system: bool = True,
    style: str = "dialog",
    group_by_date: bool = True
):
    """
    批量遍历目录下所有 JSON 文件并进行转换
    """
    abs_dir = os.path.abspath(target_dir)
    if not os.path.exists(abs_dir):
        print(f"❌ 错误：指定目录不存在 -> {abs_dir}")
        sys.exit(1)

    print(f"🔍 正在扫描目录: {abs_dir}")
    
    # 获取所有 json 文件
    pattern = "**/*.json" if recursive else "*.json"
    json_files = glob.glob(os.path.join(abs_dir, pattern), recursive=recursive)

    if not json_files:
        print(f"⚠️ 在目录 {abs_dir} 中未发现任何 .json 文件。")
        return

    print(f"📂 发现 {len(json_files)} 个 JSON 文件，开始批量处理...\n" + "-" * 50)

    success_count = 0
    skip_count = 0

    for idx, jf in enumerate(json_files, 1):
        rel_path = os.path.relpath(jf, abs_dir)
        print(f"[{idx}/{len(json_files)}] 正在处理: {rel_path} ...", end=" ")
        
        # 默认输出到用户指定的输出目录，或 JSON 文件同级目录
        out_target = output_dir if output_dir else os.path.dirname(jf)
        
        ok, result = convert_single_json(
            input_path=jf,
            output_dir=out_target,
            include_system=include_system,
            style=style,
            group_by_date=group_by_date
        )

        if ok:
            success_count += 1
            print(f"✅ 成功 -> {os.path.basename(result)}")
        else:
            skip_count += 1
            print(f"⏭️ {result}")

    print("-" * 50)
    print(f"🎉 批量处理完成！共扫描: {len(json_files)} 个，成功: {success_count} 个，跳过: {skip_count} 个。")


def main():
    parser = argparse.ArgumentParser(
        description="微信聊天记录 JSON 批量转 Markdown 工具（默认自动处理当前目录下所有 JSON）"
    )
    parser.add_argument(
        "-d", "--dir",
        default=".",
        help="指定包含 JSON 文件的目标目录（默认：当前目录 '.'）"
    )
    parser.add_argument(
        "-f", "--file",
        default=None,
        help="仅指定单个 JSON 文件进行转换（若不提供，则默认遍历整个目录）"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="输出 Markdown 文件的目录（默认保存在与 JSON 文件同目录或当前目录下）"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="是否递归扫描子目录下的 JSON 文件"
    )
    parser.add_argument(
        "--no-system",
        action="store_true",
        help="是否过滤掉系统消息（如撤回消息、添加好友提示等）"
    )
    parser.add_argument(
        "--style",
        choices=["dialog", "list", "table"],
        default="dialog",
        help="排版风格: dialog(对话块, 默认), list(列表), table(表格)"
    )
    parser.add_argument(
        "--no-date-group",
        action="store_true",
        help="不按日期分组二级标题"
    )

    args = parser.parse_args()

    # 如果显式指定了单个文件
    if args.file:
        if not os.path.exists(args.file):
            print(f"❌ 错误：指定的文件不存在 -> {args.file}")
            sys.exit(1)
        ok, res = convert_single_json(
            input_path=args.file,
            output_dir=args.output_dir,
            include_system=not args.no_system,
            style=args.style,
            group_by_date=not args.no_date_group
        )
        if ok:
            print(f"✅ 转换成功！输出至: {res}")
        else:
            print(f"❌ 转换失败: {res}")
        return

    # 默认行为或指定目录行为：扫描并转换目录下所有 JSON 文件
    process_directory(
        target_dir=args.dir,
        output_dir=args.output_dir,
        recursive=args.recursive,
        include_system=not args.no_system,
        style=args.style,
        group_by_date=not args.no_date_group
    )


if __name__ == "__main__":
    main()
