"""Reusable visual components for the GamePath Recruit frontend."""

from __future__ import annotations

import base64
import html
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from frontend.core import ROOT


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def install_theme():
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
    hero = (ROOT / "frontend" / "assets" / "operative.svg").read_bytes()
    encoded = base64.b64encode(hero).decode("ascii")
    # st.html is designed for raw HTML/CSS. st.markdown can display CSS as
    # visible text when the CSS contains paragraph breaks (e.g., blank lines).
    st.html(f'<style>:root{{--hero-image:url("data:image/svg+xml;base64,{encoded}");}}</style><style>{styles}</style>')


def sidebar_brand():
    icon = (ROOT / "frontend" / "assets" / "mark.svg").read_text(encoding="utf-8")
    st.markdown(f'<div class="gp-sidebrand">{icon}<div><strong>GAMEPATH</strong><span>RECRUIT / DIVISION</span></div></div>', unsafe_allow_html=True)


def sidebar_divider(label: str):
    st.markdown(f'<div class="gp-side-section">{esc(label)}</div>', unsafe_allow_html=True)


def sidebar_footer():
    st.markdown('<div class="gp-sidebar-bottom"><span class="dot">&#9679;</span> SISTEMA LOCAL / DEMOSTRACION<br>Grafos dirigidos + arbol binario<br>GamePath Recruit &copy; 2026</div>', unsafe_allow_html=True)


def topline(section: str, label: str = "SISTEMA OPERATIVO"):
    st.markdown(f'<div class="gp-topline"><span>GAMEPATH / <strong>{esc(section)}</strong></span><span class="gp-signal"><span class="gp-pulse"></span>{esc(label)}</span></div>', unsafe_allow_html=True)


def hero(kicker: str, title: str, body: str, *, compact: bool = False, meta: str = "RECRUITMENT SYSTEM // VALORANT"):
    clazz = 'gp-hero gp-hero-compact' if compact else 'gp-hero'
    st.markdown(f'''<section class="{clazz}">
        <div class="gp-hero-v">V</div><div class="gp-hero-art"></div>
        <div class="gp-hero-content"><span class="gp-kicker">{esc(kicker)}</span>
        <h1>{title}</h1><p>{esc(body)}</p>
        <div class="gp-hero-meta"><span><b>&#9670;</b> {esc(meta)}</span></div></div></section>''', unsafe_allow_html=True)


def heading(title: str, subtitle: str = ""):
    st.markdown(f'<div class="gp-heading"><h2>{esc(title)}</h2><span class="gp-meta">{esc(subtitle)}</span></div>', unsafe_allow_html=True)


def metric(number: str | int, title: str, subtitle: str, color: str = ""):
    st.markdown(f'<div class="gp-stat {esc(color)}"><div class="num">{esc(number)}</div><div class="name">{esc(title)}</div><div class="sub">{esc(subtitle)}</div></div>', unsafe_allow_html=True)


def tag(label: str, color: str = "slate") -> str:
    return f'<span class="gp-tag {esc(color)}">{esc(label)}</span>'


def status_color(stage: str) -> str:
    if stage in ("Oportunidades", "Entrenamiento"):
        return "green"
    if stage in ("Orientacion", "No admitido", "Reevaluacion no aprobada", "Revision suspendida"):
        return "red"
    if stage in ("Reevaluacion", "Mas evidencia"):
        return "gold"
    return "slate"


def player_card(summary, *, minimal: bool = False):
    p = summary.applicant
    initial = ''.join(x[0].upper() for x in p.game_name.split('#')[0].split()[:2])[:2] or "GP"
    stage = tag(summary.stage, status_color(summary.stage))
    st.markdown(f'''<div class="gp-player"><div class="gp-avatar">{esc(initial)}</div>
       <div class="gp-player-info"><div class="gp-player-name">{esc(p.game_name)}</div>
       <div class="gp-player-meta">{esc(p.preferred_role or 'Sin rol')} &nbsp; / &nbsp; {esc(p.applicant_id)} &nbsp; / &nbsp; {stage}</div></div>
       <div class="gp-rank"><strong>{esc(p.peak_rank)}</strong><span>PEAK RANK</span></div></div>''', unsafe_allow_html=True)


def insight(title: str, detail: str):
    st.markdown(f'<div class="gp-insight"><span style="color:#ff6674;font-weight:900;font-size:15px">&#9670;</span><span><strong>{esc(title)}</strong><br>{esc(detail)}</span></div>', unsafe_allow_html=True)


def empty(title: str, message: str):
    st.markdown(f'<div class="gp-empty"><div class="headline">{esc(title)}</div><p>{esc(message)}</p></div>', unsafe_allow_html=True)


def pipeline(counts: dict[str, int]):
    steps = [
        ("Registrados", counts.get("total", 0)),
        ("Preseleccionados", counts.get("preselected", 0)),
        ("En revision", counts.get("review", 0)),
        ("Entrenando", counts.get("training", 0)),
        ("Oportunidades", counts.get("opportunities", 0)),
    ]
    rows = ''.join(f'<div class="gp-pipe-node {"active" if i == 0 or c else ""}"><div class="count">{c:02d}</div><div class="lbl">{esc(label)}</div></div>' for i, (label, c) in enumerate(steps))
    st.markdown(f'<div class="gp-pipeline">{rows}</div>', unsafe_allow_html=True)


def profile_hero(p, status: str):
    st.markdown(f'''<div class="gp-profile-hero"><div class="gp-eyebrow">ASPIRANTE // {esc(p.applicant_id)}</div>
       <h1>{esc(p.game_name)}</h1><div class="subtitle">{esc(p.preferred_role or 'ROL SIN ESPECIFICAR').upper()} &nbsp; &bull; &nbsp; PEAK {esc(p.peak_rank).upper()} &nbsp; &bull; &nbsp; {esc(status).upper()}</div></div>''', unsafe_allow_html=True)


def details_box(title: str, rows: list[tuple[str, str]]):
    items = ''.join(f'<div style="display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid #2b3b4a;padding:11px 0;font-size:11px"><span style="color:#9bb0bb">{esc(k)}</span><strong style="text-align:right;color:#f0ece6">{esc(v)}</strong></div>' for k,v in rows)
    st.markdown(f'<div class="gp-panel"><div class="gp-panel-title">{esc(title)}</div>{items}</div>', unsafe_allow_html=True)


def decision_path(path: list[dict], classification: str, status: str):
    cells = []
    for i, step in enumerate(path, 1):
        answer = step['answer']
        color = 'green' if answer == 'S\u00ed' else 'red'
        cells.append(f'''<div class="gp-step"><span class="step-id">{esc(step['node_id'])}</span><div>
          <strong>{esc(step['question'])}</strong><div class="desc">Respuesta: {tag(answer,color)}</div></div></div>''')
    cells.append(f'''<div class="gp-step"><span class="step-id">FIN</span><div>
      <strong>{esc(classification)}</strong><div class="desc">{tag('PRESELECCIONADO' if status == 'preselected' else 'ORIENTACION', 'green' if status == 'preselected' else 'gold')}</div></div></div>''')
    st.markdown('<div class="gp-panel"><div class="gp-panel-title">Recorrido real del arbol de decision</div>' + ''.join(cells) + '</div>', unsafe_allow_html=True)


def skill_bar(skill: str, value: int):
    st.markdown(f'<div class="gp-skill"><div class="gp-skill-top"><span>{esc(skill)}</span><span>{value} / 5</span></div><div class="gp-skill-bar"><span style="width:{value * 20}%"></span></div></div>', unsafe_allow_html=True)


def completion_bar(skill: str, completed: bool):
    """Binary verified training completion; never displayed as a VOD score."""
    state = "VERIFICADO" if completed else "PENDIENTE"
    width = 100 if completed else 0
    color = "#5fe2c2" if completed else "#ff6674"
    st.markdown(
        f'<div class="gp-skill"><div class="gp-skill-top"><span>{esc(skill)}</span>'
        f'<span style="color:{color}">{state}</span></div>'
        f'<div class="gp-skill-bar"><span style="width:{width}%;background:{color}"></span></div></div>',
        unsafe_allow_html=True,
    )


def route_cards(nodes: tuple[str,...], activities: tuple[str,...], graph):
    tiles = []
    for i, node in enumerate(nodes):
        label = graph.get_node(node).label
        desc = activities[i] if i < len(activities) else 'Etapa de destino'
        tiles.append(f'<div class="gp-route-tile"><div class="n">{i+1:02d} /</div><div class="title">{esc(label)}</div><div class="desc">{esc(desc)}</div></div>')
    st.markdown('<div class="gp-route">' + ''.join(tiles) + '</div>', unsafe_allow_html=True)


def opportunity_card(idx: int, title: str, desc: str, hours: str, locked: bool):
    st.markdown(f'<div class="gp-opportunity"><div class="idx">0{idx} // {"BLOQUEADO" if locked else "DISPONIBLE"}</div><div class="title">{esc(title)}</div><div class="desc">{esc(desc)}</div><div class="hours">{esc(hours)}</div></div>', unsafe_allow_html=True)


def footer():
    st.markdown('<div class="gp-footer">GAMEPATH RECRUIT &middot; PLATAFORMA ACADEMICA DE RECLUTAMIENTO COMPETITIVO &middot; 2026<br>Interfaz original inspirada en la identidad visual del sitio oficial VALORANT. Proyecto independiente, no afiliado ni respaldado por Riot Games. Sin promesas de contratos o ingresos.</div>', unsafe_allow_html=True)


def graph_diagram(graph, route: tuple[str,...] = ()): 
    """Render source graph as vector inside a responsive embedded frame."""
    positions = {
        'training_00':(95,182), 'training_10':(275,87), 'training_01':(275,275),
        'training_11':(461,182), 'reevaluation':(655,182), 'opportunities':(846,182),
        'tournaments':(1050,65), 'tryouts':(1050,182), 'sponsorships':(1050,299),
    }
    used = set(zip(route, route[1:]))
    edges = []
    for source, p in positions.items():
        for edge in graph.outgoing_edges(source):
            if edge.target not in positions:
                continue
            dest = positions[edge.target]
            x1,y1 = p; x2,y2 = dest
            active = (source, edge.target) in used
            stroke = '#ff5665' if active else '#526473'
            bend = max(28, (x2-x1)*.45)
            edge_path = f'M{x1+63},{y1} C{x1+bend+63},{y1} {x2-bend-50},{y2} {x2-52},{y2}'
            edges.append(f'<path d="{edge_path}" fill="none" stroke="{stroke}" stroke-width="{4 if active else 2}" marker-end="url(#arr)"><title>{esc(edge.activity)} ({edge.weight_hours} h)</title></path>')
    nodes = []
    for node_id,(x,y) in positions.items():
        data = graph.get_node(node_id)
        active = node_id in route
        color = '#ff5363' if active else '#345165'
        text = {'training_00':'INICIO','training_10':'AIM','training_01':'TACTICA','training_11':'FORMACION','reevaluation':'REEVALUACION','opportunities':'ACCESO','tournaments':'TORNEOS','tryouts':'TRYOUTS','sponsorships':'SPONSORS'}[node_id]
        nodes.append(f'<g><rect x="{x-69}" y="{y-30}" width="138" height="60" rx="2" fill="{color if active else "#162735"}" stroke="{color}" stroke-width="2"/><text x="{x}" y="{y-3}" text-anchor="middle" font-size="12" font-weight="800" fill="#f3f0e9" letter-spacing="1">{text}</text><text x="{x}" y="{y+15}" text-anchor="middle" fill="#c1cbd4" font-size="10">{esc(node_id)}</text><title>{esc(data.label)}</title></g>')
    svg = f'''<svg viewBox="0 0 1160 365" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Grafo dirigido de formacion GamePath"><defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 10 5 0 10Z" fill="#ff4655"/></marker><pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="#273743" stroke-width=".65"/></pattern></defs><rect width="1160" height="365" fill="#101e29"/><rect width="1160" height="365" fill="url(#grid)"/>{''.join(edges)}{''.join(nodes)}<text x="18" y="22" font-size="11" fill="#ff7580" font-family="monospace">GRAPH / GAMEPATH_TRAINING_V1</text></svg>'''
    components.html(f'<html><body style="margin:0;background:#101e29"><div style="width:100%;overflow-x:auto;border:1px solid #334451;box-sizing:border-box"><div style="min-width:900px">{svg}</div></div></body></html>',height=400,scrolling=False)
