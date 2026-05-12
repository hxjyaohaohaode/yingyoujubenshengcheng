import logging
from datetime import UTC, datetime
from collections import defaultdict

from tasks._helpers import _safe_task_decorator as task_decorator, update_progress, push_progress_via_ws, update_agent_task_status, complete_agent_task, fail_agent_task, mark_agent_task_retrying

logger = logging.getLogger(__name__)
AGENT_NAME = "审计Agent"
TASK_NAME = "全项目审计"

DEFAULT_WEIGHTS = {
    "foreshadow_recovery": 0.15,
    "timeline_consistency": 0.10,
    "ending_reachability": 0.10,
    "character_arc": 0.10,
    "emotion_curve": 0.08,
    "cross_chapter_consistency": 0.12,
    "narrative_efficiency": 0.10,
    "conflict_evolution": 0.08,
    "satisfaction_density": 0.05,
    "genre_alignment": 0.05,
    "voice_consistency": 0.04,
    "commonsense": 0.03,
}


@task_decorator(bind=True, max_retries=1, time_limit=3600, name="tasks.full_audit.full_audit_task")
def full_audit_task(self, project_id: str, custom_weights: dict | None = None):
    task_id = self.request.id
    logger.info("full_audit_task started | task_id=%s project_id=%s", task_id, project_id)

    update_progress(task_id, 0, "running", "启动全项目审计...", agent_name=AGENT_NAME, task_name=TASK_NAME)
    push_progress_via_ws(project_id, task_id, 0, "running", "启动全项目审计...", agent_name=AGENT_NAME, task_name=TASK_NAME)

    weights = {**DEFAULT_WEIGHTS, **(custom_weights or {})}
    total_weight = sum(weights.values())
    if total_weight > 0:
        weights = {k: v / total_weight for k, v in weights.items()}

    try:
        update_agent_task_status(project_id, task_id, "full_audit", AGENT_NAME, "running")

        update_progress(task_id, 5, "running", "加载项目数据...", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 5, "running", "加载项目数据...", agent_name=AGENT_NAME, task_name=TASK_NAME)

        project_data = _load_project_data(project_id)
        target_word_count = _load_target_word_count(project_id)
        genre = _load_genre(project_id)
        core_contradiction = _load_core_contradiction(project_id)

        reports = {}
        progress = 10
        step = 75 // 12

        dimensions = [
            ("foreshadow_recovery", "计算伏笔回收率...", _analyze_foreshadow_recovery),
            ("timeline_consistency", "检查时间线连续性...", _analyze_timeline_consistency),
            ("ending_reachability", "分析结局可达性...", _analyze_ending_reachability),
            ("character_arc", "评估角色弧完整性...", _analyze_character_arcs),
            ("emotion_curve", "分析情感曲线...", _analyze_emotion_curve),
            ("narrative_efficiency", "检测叙事效率/水文...", _analyze_narrative_efficiency),
            ("conflict_evolution", "追踪冲突演进...", _analyze_conflict_evolution),
            ("cross_chapter_consistency", "检查跨章一致性...", _analyze_cross_chapter),
            ("satisfaction_density", "分析爽点/反转密度...", _analyze_satisfaction_density),
            ("genre_alignment", "校验体裁对齐...", _analyze_genre_alignment),
            ("voice_consistency", "检测叙事声音一致性...", _analyze_voice_consistency),
            ("commonsense", "执行常识合规检查...", _analyze_commonsense),
        ]

        for dim_key, label, analyzer in dimensions:
            progress += step
            update_progress(task_id, min(progress, 85), "running", label, agent_name=AGENT_NAME, task_name=TASK_NAME)
            push_progress_via_ws(project_id, task_id, min(progress, 85), "running", label, agent_name=AGENT_NAME, task_name=TASK_NAME)
            reports[dim_key] = analyzer(project_id, project_data, target_word_count, genre, core_contradiction)

        update_progress(task_id, 95, "running", "生成综合报告...", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 95, "running", "生成综合报告...", agent_name=AGENT_NAME, task_name=TASK_NAME)

        overall_score = _calculate_overall_score_weighted(reports, weights, target_word_count)

        report = {
            "task_id": task_id,
            "project_id": project_id,
            "overall_score": overall_score,
            "target_word_count": target_word_count,
            "genre": genre,
            "weights_used": {k: round(v * 100, 1) for k, v in weights.items() if v > 0},
            "dimensions": reports,
            "summary": _generate_comprehensive_summary(overall_score, reports, target_word_count),
            "generated_at": datetime.now(UTC).isoformat(),
        }

        complete_agent_task(project_id, task_id, report)

        update_progress(task_id, 100, "completed", "全项目审计完成", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 100, "completed", "全项目审计完成", agent_name=AGENT_NAME, task_name=TASK_NAME)

        logger.info("full_audit_task completed | task_id=%s overall_score=%d", task_id, overall_score)
        return report

    except Exception as e:
        logger.error("full_audit_task failed | task_id=%s error=%s", task_id, str(e), exc_info=True)
        if self.request.retries < self.max_retries:
            mark_agent_task_retrying(project_id, task_id, str(e))
            update_progress(task_id, 0, "retrying", str(e)[:200], agent_name=AGENT_NAME, task_name=TASK_NAME)
            push_progress_via_ws(project_id, task_id, 0, "retrying", str(e)[:200], agent_name=AGENT_NAME, task_name=TASK_NAME)
            raise self.retry(exc=e)

        fail_agent_task(project_id, task_id, str(e))
        update_progress(task_id, 0, "failed", str(e)[:200], agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 0, "failed", str(e)[:200], agent_name=AGENT_NAME, task_name=TASK_NAME)
        raise


def _load_project_data(project_id: str) -> dict:
    data = {
        "scenes": [], "foreshadows": [], "characters": [],
        "emotion_curves": [], "chapters": [], "relations": [],
    }

    try:
        from models.scene import Scene
        from database import get_db_sync
        with get_db_sync() as db:
            scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_code).all()
            for s in scenes:
                data["scenes"].append({
                    "id": str(s.id),
                    "chapter_id": str(s.chapter_id) if s.chapter_id else None,
                    "scene_code": s.scene_code,
                    "location": s.location or "",
                    "time_start": s.time_start or "",
                    "time_end": s.time_end or "",
                    "emotion_level": s.emotion_level or 5,
                    "narration": s.narration or "",
                    "dialogue": s.dialogue or [],
                    "foreshadow_ops": s.foreshadow_ops or [],
                    "characters_involved": s.characters_involved or [],
                    "choices": s.choices or [],
                    "is_wow_moment": bool(s.is_wow_moment),
                    "wow_type": s.wow_type or "",
                    "status": s.status or "draft",
                })
    except Exception as e:
        logger.warning("Failed to load scenes: %s", e)

    try:
        from models.foreshadow import Foreshadow, ForeshadowRelation
        from database import get_db_sync
        with get_db_sync() as db:
            foreshadows = db.query(Foreshadow).filter(Foreshadow.project_id == project_id).all()
            for fs in foreshadows:
                data["foreshadows"].append({
                    "id": str(fs.id), "fs_code": fs.fs_code, "name": fs.name,
                    "fs_type": fs.fs_type, "current_status": fs.current_status or "design",
                    "plant_scene_id": str(fs.plant_scene_id) if fs.plant_scene_id else None,
                    "reveal_scene_id": str(fs.reveal_scene_id) if fs.reveal_scene_id else None,
                    "reinforce_count": fs.reinforce_count or 0,
                    "health": fs.health or "normal",
                    "depends_on": fs.depends_on or [],
                    "enables": fs.enables or [],
                    "reinforce_scenes": fs.reinforce_scenes or [],
                })
            relations = db.query(ForeshadowRelation).filter(ForeshadowRelation.project_id == project_id).all()
            for rel in relations:
                data["relations"].append({"from": str(rel.from_fs_id), "to": str(rel.to_fs_id), "type": rel.relation_type})
    except Exception as e:
        logger.warning("Failed to load foreshadows: %s", e)

    try:
        from models.character import Character
        from database import get_db_sync
        with get_db_sync() as db:
            characters = db.query(Character).filter(Character.project_id == project_id).all()
            for char in characters:
                data["characters"].append({
                    "id": str(char.id), "name": char.name,
                    "role_type": char.role_type or "",
                    "core_goal": char.core_goal or "",
                    "arc_description": char.arc_description or "",
                    "status": char.status or "active",
                    "language_style": getattr(char, "language_style", "") or "",
                    "catchphrase": getattr(char, "catchphrase", "") or "",
                })
    except Exception as e:
        logger.warning("Failed to load characters: %s", e)

    try:
        from models.emotion_curve import EmotionCurve
        from database import get_db_sync
        with get_db_sync() as db:
            curves = db.query(EmotionCurve).filter(EmotionCurve.project_id == project_id).order_by(EmotionCurve.position_order).all()
            for ec in curves:
                data["emotion_curves"].append({
                    "id": str(ec.id), "chapter_id": str(ec.chapter_id) if ec.chapter_id else None,
                    "scene_id": str(ec.scene_id) if ec.scene_id else None,
                    "target_emotion": ec.target_emotion, "actual_emotion": ec.actual_emotion,
                    "is_wow_moment": bool(ec.is_wow_moment), "position_order": ec.position_order,
                })
    except Exception as e:
        logger.warning("Failed to load emotion curves: %s", e)

    try:
        from models.chapter import Chapter
        from database import get_db_sync
        with get_db_sync() as db:
            chapters = db.query(Chapter).filter(Chapter.project_id == project_id).order_by(Chapter.chapter_number).all()
            for ch in chapters:
                data["chapters"].append({
                    "id": str(ch.id), "chapter_number": ch.chapter_number,
                    "title": ch.title or "", "emotion_target": ch.emotion_target or 5,
                    "status": ch.status or "draft",
                })
    except Exception as e:
        logger.warning("Failed to load chapters: %s", e)

    return data


def _load_target_word_count(project_id: str) -> int:
    try:
        from models.project_config import ProjectConfig
        from database import get_db_sync
        with get_db_sync() as db:
            config = db.query(ProjectConfig).filter(ProjectConfig.project_id == project_id).first()
            if config:
                return getattr(config, "target_word_count", 0) or 0
    except Exception as e:
        logger.warning("Failed to load target_word_count: %s", e)
    return 0


def _load_genre(project_id: str) -> str:
    try:
        from models.project_config import ProjectConfig
        from database import get_db_sync
        with get_db_sync() as db:
            config = db.query(ProjectConfig).filter(ProjectConfig.project_id == project_id).first()
            if config:
                return getattr(config, "genre", "") or ""
    except Exception as e:
        logger.warning("Failed to load genre: %s", e)
    return ""


def _load_core_contradiction(project_id: str) -> str:
    try:
        from models.project_config import ProjectConfig
        from database import get_db_sync
        with get_db_sync() as db:
            config = db.query(ProjectConfig).filter(ProjectConfig.project_id == project_id).first()
            if config:
                return getattr(config, "core_contradiction", "") or ""
    except Exception as e:
        logger.warning("Failed to load core_contradiction: %s", e)
    return ""


def _analyze_foreshadow_recovery(project_id, data, *args) -> dict:
    foreshadows = data.get("foreshadows", [])
    total = len(foreshadows)
    if total == 0:
        return {"total": 0, "recovered": 0, "pending": 0, "recovery_rate": 100.0, "pass": True, "details": "暂无伏笔数据", "score": 100}
    recovered = sum(1 for fs in foreshadows if fs.get("current_status") in ("reveal", "verify"))
    pending = total - recovered
    recovery_rate = (recovered / total) * 100 if total > 0 else 100.0
    health_counts = defaultdict(int)
    for fs in foreshadows:
        health_counts[fs.get("health", "normal")] += 1
    weak = [f"{fs.get('fs_code', '?')}: {fs.get('name', '?')}" for fs in foreshadows if fs.get("reinforce_count", 0) < 2 and fs.get("current_status") not in ("reveal", "verify")]
    return {"total": total, "recovered": recovered, "pending": pending, "recovery_rate": round(recovery_rate, 1), "score": round(recovery_rate, 1), "pass": recovery_rate >= 90.0, "health_distribution": dict(health_counts), "weak_foreshadows": weak, "suggestion": "目标回收率100%，" + ("达标" if recovery_rate >= 90 else "未达标，请检查未回收伏笔")}


def _analyze_timeline_consistency(project_id, data, *args) -> dict:
    scenes = data.get("scenes", [])
    issues = []
    for i in range(len(scenes) - 1):
        curr, next_s = scenes[i], scenes[i + 1]
        if curr.get("chapter_id") != next_s.get("chapter_id"):
            continue
        ce, ns = curr.get("time_end", ""), next_s.get("time_start", "")
        if ce and ns and ce > ns:
            issues.append(f"{curr.get('scene_code', '?')}-{next_s.get('scene_code', '?')}: 时间倒退 ({ce} > {ns})")
    total = len(scenes)
    ic = len(issues)
    cr = round((1 - ic / max(total - 1, 1)) * 100, 1)
    return {"total_scenes": total, "issues_found": ic, "consistency_rate": cr, "score": cr, "pass": ic == 0, "issues": issues, "suggestion": "时间线" + ("一致" if ic == 0 else f"存在{ic}处不一致")}


def _analyze_ending_reachability(project_id, data, *args) -> dict:
    scenes = data.get("scenes", [])
    foreshadows = data.get("foreshadows", [])
    if not scenes:
        return {"total_scenes": 0, "score": 100, "pass": True, "details": "暂无场景数据"}
    graph = _build_scene_graph(scenes)
    unreachable = []
    for fs in foreshadows:
        rid = fs.get("reveal_scene_id")
        if rid is None:
            continue
        if not _is_reachable(graph, fs.get("plant_scene_id"), rid):
            unreachable.append(f"{fs.get('fs_code', '?')}: {fs.get('name', '?')}")
    t = len([fs for fs in foreshadows if fs.get("reveal_scene_id")])
    u = len(unreachable)
    rr = round((1 - u / max(t, 1)) * 100, 1)
    return {"total_scenes": len(scenes), "foreshadows_with_reveal_target": t, "unreachable_reveals": u, "reachability_rate": rr, "score": rr, "pass": u == 0, "unreachable_foreshadows": unreachable, "suggestion": "所有结局伏笔均可到达" if u == 0 else f"{u}个伏笔揭示场景不可达"}


def _build_scene_graph(scenes):
    sids = [s.get("id") for s in scenes]
    return {sid: sids[i + 1:i + 3] for i, sid in enumerate(sids)}


def _is_reachable(graph, start, end):
    if start is None or end is None:
        return True
    if start == end:
        return True
    if start not in graph or end not in graph:
        return False
    visited, queue = {start}, [start]
    while queue:
        cur = queue.pop(0)
        if cur == end:
            return True
        for nb in graph.get(cur, []):
            if nb not in visited:
                visited.add(nb)
                queue.append(nb)
    return False


def _analyze_character_arcs(project_id, data, *args) -> dict:
    chars = data.get("characters", [])
    scenes = data.get("scenes", [])
    if not chars:
        return {"total_characters": 0, "score": 100, "pass": True, "details": "暂无角色数据"}
    csc = defaultdict(int)
    for s in scenes:
        for cid in s.get("characters_involved", []):
            csc[cid] += 1
    assessments, incomplete = [], []
    for c in chars:
        cid = c.get("id")
        sc = csc.get(cid, 0)
        arc_ok = bool(c.get("arc_description")) and sc >= 3 if c.get("status") == "active" else True
        assessments.append({"name": c.get("name", "?"), "role_type": c.get("role_type", ""), "scenes_count": sc, "arc_complete": arc_ok})
        if not arc_ok:
            incomplete.append(c.get("name", "?"))
    complete = sum(1 for a in assessments if a["arc_complete"])
    cr = round(complete / max(len(chars), 1) * 100, 1)
    return {"total_characters": len(chars), "complete_arcs": complete, "completeness_rate": cr, "score": cr, "pass": len(incomplete) == 0, "assessments": assessments, "incomplete_characters": incomplete, "suggestion": "所有角色弧完整" if not incomplete else f"角色弧不完整: {', '.join(incomplete)}"}


def _analyze_emotion_curve(project_id, data, *args) -> dict:
    scenes = data.get("scenes", [])
    curves = data.get("emotion_curves", [])
    emotions = [(ec.get("target_emotion") or 0, ec.get("actual_emotion") or 0) for ec in curves] if curves else [(s.get("emotion_level") or 5, s.get("emotion_level") or 5) for s in scenes]
    if not emotions:
        return {"total_points": 0, "score": 100, "pass": True, "details": "暂无情感数据"}
    devs = [abs(t - a) for t, a in emotions]
    ad = sum(devs) / len(devs)
    ld = [f"点{i+1}: 目标={t} 实际={a} 偏差={abs(t-a)}" for i, (t, a) in enumerate(emotions) if abs(t - a) > 2]
    wm_count = sum(1 for s in scenes if s.get("is_wow_moment"))
    s = max(0, 100 - ad * 10)
    return {"total_points": len(emotions), "average_deviation": round(ad, 2), "score": round(s, 1), "pass": ad <= 2.0, "large_deviations": ld, "wow_moments_count": wm_count, "suggestion": "情感曲线整体合理" if ad <= 2.0 else f"平均偏差{ad:.1f}，建议调整{len(ld)}处异常点"}


def _analyze_narrative_efficiency(project_id, data, target_word_count, *args) -> dict:
    from checkers.narrative_efficiency import check_narrative_efficiency
    scenes = data.get("scenes", [])
    twc = target_word_count or 0
    if twc > 0 and twc <= 50000:
        min_beats, max_static = 3.0, 0.30
    elif twc > 50000 and twc <= 200000:
        min_beats, max_static = 2.5, 0.35
    elif twc > 200000:
        min_beats, max_static = 2.0, 0.40
    else:
        min_beats, max_static = 3.0, 0.30
    r = check_narrative_efficiency(scenes, target_word_count=twc, min_beats_per_1000=min_beats, max_static_ratio=max_static)
    r["score"] = round(max(0, min(100, r.get("beats_per_1000", 0) / max(min_beats, 0.1) * 70 + (1 - r.get("static_ratio", 0)) * 30)), 1)
    return r


def _analyze_conflict_evolution(project_id, data, *args):
    from checkers.conflict_evolution import check_conflict_evolution
    core = args[-1] if args else ""
    scenes = data.get("scenes", [])
    r = check_conflict_evolution(scenes, core)
    score = 60
    if r["pass"]:
        score = 85
    elif r.get("dropped_warning"):
        score = 25
    elif r.get("flat_warning"):
        score = 45
    score += min(r.get("evolution_score", 0), 15)
    r["score"] = min(round(score, 1), 100)
    return r


def _analyze_cross_chapter(project_id, data, *args):
    from checkers.cross_chapter_consistency import check_cross_chapter_consistency
    scenes = data.get("scenes", [])
    chars = data.get("characters", [])
    foreshadows = data.get("foreshadows", [])
    r = check_cross_chapter_consistency(scenes, chars, foreshadows)
    ti = r.get("total_issues", 0)
    score = max(0, 100 - ti * 5)
    r["score"] = min(round(score, 1), 100)
    return r


def _analyze_satisfaction_density(project_id, data, target_word_count, *args):
    from checkers.satisfaction_density import check_satisfaction_density
    scenes = data.get("scenes", [])
    r = check_satisfaction_density(scenes)
    avg = r.get("avg_wow_per_chapter", 0)
    target = r.get("target_beats_per_chapter", 2.5)
    score = min(100, round(avg / max(target, 0.1) * 70, 1))
    r["score"] = score
    return r


def _analyze_genre_alignment(project_id, data, target_word_count, genre, *args):
    from checkers.genre_alignment import check_genre_alignment
    scenes = data.get("scenes", [])
    core = (args[-1] if args else "") or genre
    r = check_genre_alignment(scenes, genre=genre or "", core_contradiction=core)
    mc = r.get("must_element_coverage", 0)
    ta = r.get("tone_alignment", 0)
    score = min(100, round(mc * 0.6 + ta * 0.4, 1))
    r["score"] = score
    return r


def _analyze_voice_consistency(project_id, data, *args):
    from checkers.voice_consistency import check_voice_consistency
    scenes = data.get("scenes", [])
    chars = data.get("characters", [])
    r = check_voice_consistency(scenes, chars)
    ti = r.get("total_issues", 0)
    score = max(0, 100 - ti * 10)
    r["score"] = min(round(score, 1), 100)
    return r


def _analyze_commonsense(project_id, data, *args):
    from checkers.commonsense_validator import check_commonsense
    scenes = data.get("scenes", [])
    chars = data.get("characters", [])
    r = check_commonsense(scenes, chars)
    tv = r.get("total_violations", 0)
    score = max(0, 100 - tv * 15)
    r["score"] = min(round(score, 1), 100)
    return r


def _calculate_overall_score_weighted(reports, weights, target_word_count):
    total = 0.0
    for dim_key, weight in weights.items():
        report = reports.get(dim_key, {})
        score = report.get("score", 50)
        total += score * weight
    return int(total)


def _generate_comprehensive_summary(overall_score, reports, target_word_count):
    grade = "优秀" if overall_score >= 90 else "良好" if overall_score >= 75 else "一般" if overall_score >= 60 else "需改进"

    dim_lines = []
    labels = {
        "foreshadow_recovery": "伏笔回收率",
        "timeline_consistency": "时间线一致性",
        "ending_reachability": "结局可达性",
        "character_arc": "角色弧完整性",
        "emotion_curve": "情感曲线",
        "narrative_efficiency": "叙事效率/水文检测",
        "conflict_evolution": "冲突演进",
        "cross_chapter_consistency": "跨章一致性",
        "satisfaction_density": "爽点/反转密度",
        "genre_alignment": "体裁对齐",
        "voice_consistency": "叙事声音一致性",
        "commonsense": "常识合规",
    }

    for dim_key, label in labels.items():
        r = reports.get(dim_key, {})
        score = r.get("score", "-")
        status = "✓" if r.get("pass", False) else "✗"
        dim_lines.append(f"  [{status}] {label}: {score}分")

    word_info = ""
    if target_word_count:
        actual_words = reports.get("narrative_efficiency", {}).get("total_words", 0)
        progress_pct = round(actual_words / max(target_word_count, 1) * 100, 1)
        word_info = f"\n字数进度: {actual_words} / {target_word_count} ({progress_pct}%)"

    all_pass = all(r.get("pass", False) for r in reports.values())
    verdict = "所有维度均已达标，项目质量良好。" if all_pass else "部分维度未达标，请参阅详细报告。"

    return f"综合评分: {overall_score}/100 ({grade}){word_info}\n各维度评分:\n" + "\n".join(dim_lines) + "\n\n{verdict}"
