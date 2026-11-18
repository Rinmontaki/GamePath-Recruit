"""GamePath Recruit: responsive VALORANT-inspired Streamlit frontend.

Run from repository root: streamlit run frontend/app.py
Every business decision is delegated to backend services and SQLite.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import plotly.graph_objects as go
import streamlit as st

from frontend.core import GamePathFacade, RANKS, ROLES
from frontend.ui import (
    decision_path, details_box, empty, footer, graph_diagram, heading,
    hero, insight, install_theme, metric, opportunity_card, pipeline,
    player_card, profile_hero, route_cards, sidebar_brand, esc, completion_bar,
    sidebar_divider, sidebar_footer, skill_bar, status_color, tag, topline,
)

st.set_page_config(
    page_title="GamePath Recruit | Competitive Talent",
    page_icon="\U0001f3af",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "GamePath Recruit: proyecto academico independiente de Riot Games."},
)

PAGES = [
    "Centro de mando", "Aspirantes", "Nuevo aspirante", "Perfil del jugador",
    "Preseleccion", "Evaluacion de VOD", "Entrenamiento", "Reevaluacion",
    "Oportunidades", "Laboratorio de grafos", "Configuracion",
]
PAGE_GROUPS = {"RECLUTAMIENTO": PAGES[:6], "PROGRESO COMPETITIVO": PAGES[6:10], "SISTEMA": PAGES[10:]}
RANK_LABELS = {r: r.capitalize() for r in RANKS}
SKILL_LABELS = {
    "aim": "Punteria / AIM", "game_sense": "Lectura de juego",
    "rotations": "Rotaciones", "macro": "Macrojuego", "micro": "Microjuego",
    "communication": "Comunicacion",
}
VOD_SCORE_DEFAULT = 3


@st.cache_resource(show_spinner=False)
def get_facade() -> GamePathFacade:
    return GamePathFacade()


def go_to(page: str, applicant_id: str | None = None):
    st.session_state["nav_page"] = page
    st.session_state["_pending_nav_radio"] = page
    if applicant_id:
        st.session_state["selected_applicant"] = applicant_id
        for widget_key in list(st.session_state):
            if widget_key.startswith("select_"):
                del st.session_state[widget_key]
    st.rerun()


def choose_applicant(facade: GamePathFacade, *, allow_empty: bool = False,
                     key: str = "candidate", filter_stages: set[str] | None = None):
    summaries = facade.list_summaries()
    if filter_stages is not None:
        summaries = tuple(s for s in summaries if s.stage in filter_stages)
    if not summaries:
        empty("SIN CANDIDATOS DISPONIBLES", "Registra aspirantes o completa los pasos previos del proceso para habilitar esta vista.")
        return None
    options = [s.applicant.applicant_id for s in summaries]
    preferred = st.session_state.get("selected_applicant")
    default = options.index(preferred) if preferred in options else 0
    chosen = st.selectbox(
        "Seleccionar aspirante", options=options, index=default,
        format_func=lambda i: next(f"{s.applicant.game_name}  /  {s.stage}" for s in summaries if s.applicant.applicant_id == i),
        key=f"select_{key}",
    )
    st.session_state["selected_applicant"] = chosen
    return chosen


def reviewer_selector(facade: GamePathFacade, *, key: str):
    reviewers = [r for r in facade.list_reviewers() if r["is_active"]]
    if not reviewers:
        st.info("No hay reclutadores activos. En Configuracion puedes habilitar el usuario de demostracion local.")
        return None
    return st.selectbox(
        "Reclutador responsable (prototipo sin login)",
        options=[r["reviewer_id"] for r in reviewers],
        format_func=lambda i: next(r["display_name"] for r in reviewers if r["reviewer_id"] == i),
        key=f"reviewer_{key}",
    )


def safe_external_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        url = urlsplit(value)
        if url.scheme in ("http", "https") and url.netloc:
            return value
    except ValueError:
        pass
    return None


def vod_reference_box(facade: GamePathFacade, value: str | None):
    if not value:
        insight("VOD pendiente", "El aspirante debe aportar una grabacion antes de recibir una evaluacion humana.")
        return
    local = facade.local_vod_path(value)
    if local:
        st.video(str(local))
    elif value.startswith("https://example.com/demo-vod-"):
        insight("VOD de muestra", "Referencia ficticia de demostracion; reemplazala por el video de un jugador real para reproducirlo.")
    elif safe_external_url(value):
        st.link_button("ABRIR GRABACION EXTERNA", value, use_container_width=True)
    else:
        st.code(value, language=None)
        st.caption("Referencia interna. El archivo no se encuentra en esta instalacion.")


def radar_plot(review):
    if not review:
        return
    names = list(SKILL_LABELS.values())
    values = [getattr(review.scores, k) for k in SKILL_LABELS]
    fig = go.Figure(go.Scatterpolar(
        r=values + [values[0]], theta=names + [names[0]], fill="toself",
        line={"color": "#ff5263", "width": 3},
        fillcolor="rgba(255,70,85,.22)",
        marker={"color": "#ff7886", "size": 7},
        hovertemplate="%{theta}: %{r}/5<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False, height=310,
        margin=dict(l=56, r=56, t=20, b=22),
        font=dict(family="Inter", color="#cfdae1", size=10),
        polar=dict(bgcolor="rgba(0,0,0,0)",
                   radialaxis=dict(range=[0, 5], visible=True, tickvals=[1,2,3,4,5],
                                   tickfont=dict(color="#7f96a4",size=9),
                                   gridcolor="#354653", linecolor="#354653"),
                   angularaxis=dict(gridcolor="#354653", linecolor="#354653",
                                    tickfont=dict(color="#d7e0e5", size=10))),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def page_dashboard(facade: GamePathFacade):
    topline("CENTRO DE MANDO")
    hero("COMPETITIVE TALENT // RECRUITING", "EL FUTURO<br>SE <em>RECLUTA.</em>",
         "Descubre talento, evalua su potencial y construye rutas de crecimiento competitivo basadas en datos.")
    a,b,c = st.columns([1.2,1.1,4])
    with a:
        if st.button("+ REGISTRAR JUGADOR", type="primary", use_container_width=True):
            go_to("Nuevo aspirante")
    with b:
        if st.button("VER ASPIRANTES", use_container_width=True):
            go_to("Aspirantes")
    counts = facade.counts()
    heading("Estado de la division", "INDICADORES DE BASE DE DATOS")
    cols = st.columns(4, gap="small")
    for column, data in zip(cols, [
        (counts["total"], "Jugadores registrados", "Perfiles creados", ""),
        (counts["preselected"], "Preseleccionados", "Segun el arbol binario", "red"),
        (counts["training"], "En formacion", "Plan Dijkstra activo", "gold"),
        (counts["opportunities"], "Listos para competir", "Reevaluacion aprobada", "green"),
    ]):
        with column:
            metric(*data)
    heading("Pipeline de reclutamiento", "FLUJO DE SELECCION")
    pipeline(counts)
    col_left,col_right = st.columns([1.43,1],gap="large")
    with col_left:
        heading("Radar de talento", "ULTIMOS ASPIRANTES")
        players = list(facade.list_summaries())
        if not players:
            empty("EL ROSTER ESTA VACIO", "Agrega al primer jugador o carga datos de demostracion desde Configuracion para explorar el sistema completo.")
        for summary in players[-4:][::-1]:
            player_card(summary)
            if st.button("ABRIR PERFIL", key=f"dash_{summary.applicant.applicant_id}", use_container_width=True):
                go_to("Perfil del jugador", summary.applicant.applicant_id)
    with col_right:
        heading("Inteligencia del sistema", "ESTRUCTURAS NO LINEALES")
        st.markdown('''<div class="gp-panel"><div class="gp-eyebrow">01 // PERFILAMIENTO</div>
         <div class="gp-panel-title">ARBOL BINARIO</div><div class="gp-muted">Decisiones por disponibilidad, compromiso y peak rank. Clasificacion explicable en cada nodo.</div></div>
         <div class="gp-panel"><div class="gp-eyebrow">02 // PROGRESO</div><div class="gp-panel-title">GRAFO DIRIGIDO</div>
         <div class="gp-muted">Estados de formacion, aristas ponderadas y acceso condicionado a oportunidades.</div></div>
         <div class="gp-panel"><div class="gp-eyebrow">03 // ALGORITMOS</div><div class="gp-panel-title">BFS + DFS + DIJKSTRA</div>
         <div class="gp-muted">Exploracion de rutas y calculo del menor costo estimado de preparacion.</div></div>''', unsafe_allow_html=True)
        if st.button("EXPLORAR EL GRAFO", use_container_width=True):
            go_to("Laboratorio de grafos")
    insight("Decisiones con supervision humana", "La preseleccion es automatica, pero la admision, los avances y la reevaluacion requieren una valoracion del reclutador.")


def page_applicants(facade: GamePathFacade):
    topline("ASPIRANTES")
    hero("TALENT DATABASE // ROSTER", "EL <em>ROSTER</em>",
         "Gestiona perfiles, sigue su estado y abre el expediente competitivo de cada postulante.", compact=True)
    summaries = facade.list_summaries()
    left, middle, right = st.columns([2,1.2,1.2])
    with left: query = st.text_input("Buscar por ID o nombre de jugador", placeholder="Ej. NOVA#404", key="filter_search")
    with middle: stages = ["Todos"] + sorted(set(s.stage for s in summaries))
    with middle: status = st.selectbox("Estado", stages)
    with right: rank = st.selectbox("Peak rank", ["Todos"] + [r.capitalize() for r in RANKS])
    selected = [s for s in summaries if (
        (not query or query.lower() in s.applicant.game_name.lower() or query.lower() in s.applicant.applicant_id.lower())
        and (status == "Todos" or s.stage == status)
        and (rank == "Todos" or s.applicant.peak_rank == rank.lower())
    )]
    heading("Jugadores encontrados", f"{len(selected)} / {len(summaries)} REGISTROS")
    if not selected:
        empty("SIN RESULTADOS", "No hay jugadores que cumplan los filtros. Puedes modificar la busqueda o registrar un nuevo aspirante.")
    for s in selected:
        ca, cb = st.columns([5,1.2],gap="small",vertical_alignment="center")
        with ca: player_card(s)
        with cb:
            if st.button("VER PERFIL", key=f"list_{s.applicant.applicant_id}", use_container_width=True):
                go_to("Perfil del jugador", s.applicant.applicant_id)
    st.divider()
    a,b = st.columns([1.2,4])
    with a:
        if st.button("+ NUEVO ASPIRANTE", type="primary", use_container_width=True):
            go_to("Nuevo aspirante")
    with b:
        st.download_button("EXPORTAR ROSTER CSV", facade.export_csv(), file_name="gamepath_roster.csv", mime="text/csv")


def page_register(facade: GamePathFacade):
    topline("POSTULACION")
    hero("NEW TALENT // APPLICATION", "NUEVO <em>ASPIRANTE.</em>",
         "Primero el perfil competitivo. Despues, el arbol binario decide si el jugador puede avanzar a la revision de VOD.", compact=True)
    heading("Ficha de reclutamiento", "CAMPOS MARCADOS COMO OBLIGATORIOS")
    # Keep this interactive. Streamlit forms batch widget updates until submit,
    # which prevents switching between a URL field and the file uploader.
    with st.container(border=True):
        st.markdown("#### 01 / Identidad competitiva")
        c1,c2 = st.columns([1.6,1])
        with c1: game_name = st.text_input("Nombre de jugador *", placeholder="Ej. NOVA#404")
        with c2: role = st.selectbox("Rol preferido", ["Sin especificar"] + list(ROLES))
        st.markdown("#### 02 / Perfil y disponibilidad")
        c1,c2,c3 = st.columns(3)
        with c1: peak_rank = st.selectbox("Peak rank *", list(RANKS), format_func=lambda r:r.capitalize(), index=5)
        with c2: current_rank = st.selectbox("Rango actual", ["Sin especificar"] + list(RANKS), format_func=lambda r:r.capitalize(), index=0)
        with c3: daily_hours = st.number_input("Horas de juego por dia *", min_value=0.0, max_value=24.0, value=5.0, step=0.5)
        accepts = st.checkbox("Acepto seguir un programa de entrenamiento estructurado", value=True)
        st.markdown("#### 03 / Grabacion de partida (opcional)")
        mode = st.radio("Forma de agregar VOD", ["Enlace", "Subir archivo"], horizontal=True)
        url = ""
        upload = None
        if mode == "Enlace":
            url = st.text_input("Enlace a grabacion", placeholder="https://... (YouTube, Drive u otro enlace)")
        else:
            upload = st.file_uploader("Cargar grabacion - maximo 150 MB", type=["mp4", "mov", "webm", "avi"], key="register_vod_upload")
            if upload is not None:
                st.caption(f"Video seleccionado: {upload.name} ({upload.size / (1024 * 1024):.1f} MB)")
        submit = st.button("REGISTRAR Y EVALUAR PERFIL", type="primary", use_container_width=True, key="register_submit")
    if submit:
        reference = None
        try:
            if len(game_name.strip()) < 3:
                raise ValueError("El nombre del jugador debe contener al menos 3 caracteres.")
            if url.strip():
                if not safe_external_url(url.strip()):
                    raise ValueError("La URL del VOD debe comenzar por https:// o http:// y tener dominio valido.")
                reference = url.strip()
            elif upload is not None:
                reference = facade.store_vod(upload)
            p = facade.register(
                game_name=game_name, daily_play_hours=daily_hours,
                peak_rank=peak_rank, accepts_training=accepts,
                current_rank=None if current_rank == "Sin especificar" else current_rank,
                preferred_role=None if role == "Sin especificar" else role,
                vod_reference=reference,
            )
            st.success("Aspirante registrado con ID " + p.applicant_id)
            pre = facade.preselect(p.applicant_id)
            st.info(f"Preseleccion: {pre['classification']}. {pre['recommendation']}")
            st.session_state["selected_applicant"] = p.applicant_id
            st.session_state["recent_registered_id"] = p.applicant_id
        except (ValueError, sqlite3.IntegrityError, OSError) as exc:
            if reference and reference.startswith("uploads/"):
                generated_file = facade.local_vod_path(reference)
                if generated_file: generated_file.unlink(missing_ok=True)
            st.error(str(exc))
    recent_id = st.session_state.get("recent_registered_id")
    if recent_id and st.button("VER EXPEDIENTE CREADO", type="primary"):
        st.session_state.pop("recent_registered_id", None)
        go_to("Perfil del jugador", recent_id)
    insight("Preseleccion no significa admision", "El arbol filtra los criterios iniciales, pero la evaluacion del VOD y la aprobacion de ingreso dependen de un humano.")


def page_profile(facade: GamePathFacade):
    topline("EXPEDIENTE")
    chosen = choose_applicant(facade, key="profile")
    if not chosen: return
    s = facade.get_summary(chosen)
    p = s.applicant
    profile_hero(p, s.stage)
    a,b,c = st.columns(3, gap="small")
    with a: metric(p.peak_rank.upper(), "Peak rank", "Mejor rango alcanzado", "red")
    with b: metric(p.daily_play_hours, "Horas por dia", "Disponibilidad reportada", "")
    with c: metric(f"{len(s.completed_skills)*50}%", "Progreso", "Aim + tactica" if s.reviewed else "Sin admision", "green")
    col1,col2 = st.columns([1.2,1], gap="large")
    with col1:
        heading("Analisis de perfil", "ARBOL BINARIO")
        pre = facade.preselect(chosen)
        st.markdown(f'<div class="gp-panel"><div class="gp-eyebrow">CLASIFICACION</div><div class="gp-panel-title">{esc(pre["classification"])}</div><div class="gp-muted">{esc(pre["reason"])}</div></div>', unsafe_allow_html=True)
        if st.button("VER RECORRIDO DEL ARBOL", use_container_width=True):
            go_to("Preseleccion", chosen)
        heading("Evidencia VOD", "REVISION HUMANA")
        vod_reference_box(facade, p.vod_reference)
        with st.expander("Agregar o reemplazar referencia de VOD"):
            st.warning("Un nuevo VOD requiere una nueva evaluacion. El historial previo se conserva, pero no habilita el nuevo ciclo de entrenamiento.")
            option = st.radio("Origen de VOD", ["URL", "Archivo"], horizontal=True, key="profile_vod_mode")
            new_url = st.text_input("URL de VOD", key="profile_vod_url") if option == "URL" else ""
            file = st.file_uploader("Archivo de video", type=["mp4","mov","avi","webm"], key="profile_vod_file") if option == "Archivo" else None
            if st.button("GUARDAR NUEVO VOD", type="primary", key="save_profile_vod"):
                reference = None
                try:
                    if option == "URL":
                        if not safe_external_url(new_url):
                            raise ValueError("Ingresa una URL HTTP o HTTPS valida.")
                        reference = new_url
                    elif file:
                        reference = facade.store_vod(file)
                    else:
                        raise ValueError("Selecciona un archivo de video.")
                    facade.set_vod_reference(chosen, reference)
                    st.success("VOD actualizado. Se requiere una revision nueva.")
                    st.rerun()
                except (ValueError,OSError) as e: st.error(str(e))
    with col2:
        heading("Datos generales", "REGISTRO COMPETITIVO")
        details_box("Ficha del jugador", [
            ("Game name", p.game_name), ("Identificador", p.applicant_id),
            ("Peak rank", p.peak_rank.capitalize()),
            ("Rango actual", (p.current_rank or "No indicado").capitalize()),
            ("Rol", p.preferred_role or "No indicado"),
            ("Entrenamiento", "Aceptado" if p.accepts_training else "No aceptado"),
            ("Estado", s.stage),
        ])
        heading("Evaluacion de habilidades", "ULTIMA REVISION")
        review = facade.latest_review(chosen)
        if review and review.vod_reference == p.vod_reference:
            radar_plot(review)
            st.caption(f"Decision: {review.decision.value.upper()} | Evaluador: {review.reviewer_id}")
        else:
            empty("SIN VALORACION ACTUAL", "Todavia no se ha guardado una evaluacion VOD para la referencia activa.")
    if s.stage in ("Revision VOD", "Mas evidencia") and s.eligible and p.vod_reference:
        if st.button("CONTINUAR A EVALUACION VOD", type="primary"):
            go_to("Evaluacion de VOD", chosen)
    elif s.stage == "Entrenamiento":
        if st.button("ABRIR PLAN DE ENTRENAMIENTO", type="primary"):
            go_to("Entrenamiento", chosen)
    elif s.stage == "Oportunidades":
        if st.button("VER OPORTUNIDADES HABILITADAS", type="primary"):
            go_to("Oportunidades", chosen)


def page_preselection(facade: GamePathFacade):
    topline("PRESELECCION")
    hero("BINARY TREE // DECISION ENGINE", "CADA DATO<br><em>CUENTA.</em>",
         "Seguimiento transparente de cada pregunta del arbol binario: disponibilidad, compromiso y nivel competitivo.", compact=True)
    chosen = choose_applicant(facade, key="tree")
    if not chosen: return
    result = facade.preselect(chosen)
    col1,col2=st.columns([1.1,1],gap="large")
    with col1:
        heading("Trazabilidad de decisiones", f"NODO FINAL {result['node_id']}")
        decision_path(result["decision_path"], result["classification"], result["status"])
    with col2:
        heading("Resultado del perfil", "EVALUACION AUTOMATICA")
        color = "green" if result["eligible_for_vod_review"] else "gold"
        st.markdown(f'<div class="gp-panel"><div class="gp-eyebrow">{esc(result["status"].upper())}</div><div class="gp-panel-title">{esc(result["classification"])}</div><div class="gp-muted">{esc(result["reason"])}</div><div style="margin-top:18px">{tag(result["node_id"],color)}</div></div>', unsafe_allow_html=True)
        insight("Siguiente accion sugerida", str(result["recommendation"]))
        details_box("Criterios utilizados", [
            ("Horas minimas", "5 al dia"), ("Compromiso", "Entrenamiento estructurado"),
            ("Rango minimo", "Oro"), ("Nivel avanzado", "Diamante o superior"),
        ])
        if result["eligible_for_vod_review"] and st.button("CONTINUAR A REVISION DE VOD", type="primary",use_container_width=True):
            go_to("Evaluacion de VOD", chosen)
    st.caption("La regla del arbol se lee directamente de backend/data/profile_tree.json. Ningun dictamen se genera con valores inventados en la interfaz.")


def page_review(facade: GamePathFacade):
    topline("REVISION DE VOD")
    hero("HUMAN REVIEW // EVALUATION", "NO ES SUERTE.<br><em>ES TALENTO.</em>",
         "Evalua seis dimensiones competitivas de una grabacion y registra una decision humana verificable.", compact=True)
    eligibles = [s for s in facade.list_summaries() if s.eligible and s.applicant.vod_reference]
    if not eligibles:
        empty("SIN VOD PENDIENTES", "Primero registra un aspirante preseleccionado y agrega un enlace o archivo de VOD.")
        return
    chosen = choose_applicant(facade, key="vod", filter_stages={s.stage for s in eligibles})
    if not chosen: return
    p=facade.get_applicant(chosen)
    result = facade.preselect(chosen)
    if not result["eligible_for_vod_review"] or not p.vod_reference:
        st.error("Este perfil no cumple las condiciones para revision de VOD.")
        return
    col1,col2=st.columns([1.02,1.1],gap="large")
    with col1:
        heading("Fuente de evidencia", "VOD DEL ASPIRANTE")
        player = facade.get_summary(chosen)
        player_card(player)
        vod_reference_box(facade, p.vod_reference)
        last = facade.latest_review(chosen)
        if last:
            heading("Ultima decision", "HISTORIAL GUARDADO")
            st.markdown(f'<div class="gp-panel"><div class="gp-panel-title">{esc(last.decision.value.replace("_", " ").upper())}</div><div class="gp-muted">{esc(last.feedback)}</div></div>',unsafe_allow_html=True)
    with col2:
        heading("Ficha de evaluacion", "ESCALA / 1 A 5")
        reviewer=reviewer_selector(facade,key="vod")
        if reviewer is None: return
        with st.form("review_form",border=True):
            st.markdown("#### Califica las seis habilidades")
            cols=st.columns(2)
            scores = {}
            for i,(key,label) in enumerate(SKILL_LABELS.items()):
                with cols[i%2]:
                    scores[key]=st.slider(label,min_value=1,max_value=5,value=VOD_SCORE_DEFAULT,key=f"score_{key}")
            decision = st.radio("Decision del reclutador", options=["approved","more_evidence","rejected"],
                                format_func=lambda s:{"approved":"Admitir","more_evidence":"Solicitar mas evidencia","rejected":"No admitir"}[s])
            feedback=st.text_area("Retroalimentacion obligatoria",placeholder="Puntos fuertes, aspectos por mejorar y motivo de la decision...",height=98)
            send=st.form_submit_button("GUARDAR EVALUACION",type="primary",use_container_width=True)
        if send:
            try:
                review_id=facade.record_review(chosen,reviewer,decision,scores,feedback)
                st.success(f"Evaluacion #{review_id} registrada correctamente.")
                st.rerun()
            except (ValueError,PermissionError,sqlite3.IntegrityError) as exc:
                st.error(str(exc))
    insight("Criterio de ingreso", "Solo una evaluacion humana APROBADA permite crear el plan de entrenamiento en el grafo dirigido.")


def page_training(facade: GamePathFacade):
    topline("ENTRENAMIENTO")
    hero("WEIGHTED GRAPH // DIJKSTRA", "SUBE TU<br><em>NIVEL.</em>",
         "Cada avance se verifica. El algoritmo calcula la ruta de menor costo a la reevaluacion segun el progreso guardado.",compact=True)
    chosen=choose_applicant(facade,key="train")
    if not chosen:return
    s=facade.get_summary(chosen)
    try:
        plan=facade.training_plan(chosen)
    except (ValueError,PermissionError) as exc:
        st.warning(f"Plan no disponible: {exc}")
        insight("Se requiere admision previa", "El reclutador debe aprobar el VOD vigente del aspirante antes de ingresar al grafo.")
        return
    col1,col2,col3=st.columns(3)
    with col1:metric(f"{plan.estimated_hours:g} h","Tiempo pendiente","Costo minimo segun Dijkstra","red")
    with col2:metric(f"{len(plan.pending_skills)}","Habilidades pendientes","Aim + tactica","gold")
    with col3:metric(f"{(2-len(plan.pending_skills))*50}%","Progreso validado","Confirmado por reclutador","green")
    heading("Ruta personalizada calculada",f"{plan.start_node.upper()} -> {plan.target_node.upper()}")
    route_cards(plan.nodes,plan.activities,facade.graph)
    heading("Mapa de formacion","GRAFO DIRIGIDO Y PONDERADO")
    graph_diagram(facade.graph,plan.nodes)
    left,right=st.columns([1,1],gap="large")
    with left:
        heading("Habilidades del jugador","PROGRESO PERSISTENTE")
        complete=set(("aim","tactics"))-set(plan.pending_skills)
        for skill,label in (("aim","AIM / PUNTERIA"),("tactics","TACTICA / DECISIONES")):
            completion_bar(label,skill in complete)
        insight("Progreso por ciclo de VOD", "Si se registra una nueva revision del VOD, la formacion comienza un nuevo ciclo y se conserva el historial anterior.")
    with right:
        heading("Certificar avance", "REQUIERE RECLUTADOR ACTIVO")
        if not plan.pending_skills:
            st.success("Formacion completa. El aspirante puede pasar a reevaluacion humana.")
            if st.button("IR A REEVALUACION",type="primary",use_container_width=True):
                go_to("Reevaluacion",chosen)
        else:
            reviewer=reviewer_selector(facade,key="train")
            skill=st.selectbox("Habilidad terminada",options=list(plan.pending_skills),format_func=lambda x:{"aim":"Entrenamiento de aim","tactics":"Entrenamiento tactico"}[x])
            confirmed=st.checkbox("He verificado la finalizacion de esta actividad",key="confirm_training")
            if st.button("VALIDAR Y GUARDAR AVANCE", type="primary", disabled=reviewer is None or not confirmed,use_container_width=True):
                try:
                    facade.record_completion(chosen,skill,reviewer)
                    st.success("Habilidad certificada en SQLite.")
                    st.rerun()
                except (ValueError,PermissionError,sqlite3.IntegrityError) as exc:st.error(str(exc))


def page_reevaluation(facade: GamePathFacade):
    topline("REEVALUACION")
    hero("FINAL HUMAN GATE // PERFORMANCE", "EL SIGUIENTE<br><em>PASO.</em>",
         "La formacion no desbloquea automaticamente las oportunidades. Primero se requiere una reevaluacion humana.",compact=True)
    chosen=choose_applicant(facade,key="reevaluation")
    if not chosen:return
    try:
        plan=facade.training_plan(chosen)
        ready=not bool(plan.pending_skills) and plan.start_node=="training_11"
    except (ValueError,PermissionError) as exc:
        st.warning(f"No se puede reevaluar: {exc}")
        return
    col1,col2=st.columns([1,1],gap="large")
    with col1:
        heading("Condiciones de acceso", "CHECK DE ENTRENAMIENTO")
        details_box("Preparacion", [
            ("AIM completado", "SI" if "aim" not in plan.pending_skills else "NO"),
            ("Tactica completada", "SI" if "tactics" not in plan.pending_skills else "NO"),
            ("Estado", "LISTO PARA REEVALUAR" if ready else "FORMACION INCOMPLETA"),
        ])
        old=facade.latest_reevaluation(chosen)
        if old:
            heading("Ultima reevaluacion","PERSISTIDA EN SQLITE")
            insight("APROBADA" if old["approved"] else "NO APROBADA",old["feedback"])
    with col2:
        heading("Dictamen humano", "REGISTRO OBLIGATORIO")
        if not ready:
            empty("AUN NO ESTAS LISTO", "Se deben certificar las dos competencias de entrenamiento antes de la reevaluacion.")
            return
        reviewer=reviewer_selector(facade,key="reevaluation")
        if reviewer is None:return
        with st.form("form_reevaluation"):
            approved=st.radio("Resultado de la reevaluacion",[True,False],format_func=lambda x:"APROBADO: habilitar oportunidades" if x else "NO APROBADO: continuar fortalecimiento")
            feedback=st.text_area("Concepto del reclutador",placeholder="Evaluacion de progreso, evidencias y recomendacion final...",height=110)
            send=st.form_submit_button("REGISTRAR REEVALUACION",type="primary",use_container_width=True)
        if send:
            try:
                reevaluation_id=facade.record_reevaluation(chosen,reviewer,approved,feedback)
                st.success(f"Reevaluacion #{reevaluation_id} guardada.")
                st.rerun()
            except (ValueError,PermissionError,sqlite3.IntegrityError) as exc:st.error(str(exc))


def page_opportunities(facade: GamePathFacade):
    topline("OPORTUNIDADES")
    hero("TALENT PATHWAY // OPPORTUNITIES", "CONQUISTA TU<br><em>PROXIMO NIVEL.</em>",
         "El sistema orienta hacia tres caminos competitivos. El acceso requiere formacion y reevaluacion aprobadas.",compact=True)
    chosen=choose_applicant(facade,key="opp")
    if not chosen:return
    routes=[]
    error=None
    try: routes=facade.opportunities(chosen)
    except (PermissionError,ValueError) as exc: error=str(exc)
    unlocked=bool(routes)
    if unlocked:
        st.success("ACCESO DESBLOQUEADO - El aspirante cuenta con reevaluacion vigente aprobada.")
    else:
        st.warning("OPORTUNIDADES BLOQUEADAS: " + (error or "No disponible"))
    known={r.opportunity_id:r for r in routes}
    data=[
        ("tournaments","TORNEOS CON PREMIOS","Preparacion para convocatorias competitivas y torneos con posibles premios."),
        ("tryouts","PRUEBAS EN EQUIPOS","Preparacion de VOD y curriculum para futuras pruebas de seleccion."),
        ("sponsorships","PATROCINIO","Preparacion de un dossier y propuesta para potenciales aliados."),
    ]
    heading("Rutas de oportunidad", "CONDICIONADAS A EVALUACION HUMANA")
    cols=st.columns(3,gap="small")
    for idx,((route_id,label,desc),column) in enumerate(zip(data,cols),1):
        with column:
            info=known.get(route_id)
            hour=f"COSTO DE PREPARACION: {info.estimated_hours:g} HORAS" if info else "ACCESO RESTRINGIDO"
            opportunity_card(idx,label,desc,hour,locked=info is None)
    if unlocked:
        heading("Preparacion recomendada", "RUTAS CALCULADAS POR DIJKSTRA")
        choice=st.selectbox("Explorar camino habilitado",routes,format_func=lambda r:r.label)
        route_cards(choice.nodes,choice.activities,facade.graph)
        st.caption("La aplicacion no inscribe en eventos ni genera contratos ni patrocinios. Presenta rutas de preparacion, no oportunidades verificadas de terceros.")
    insight("Orientacion, no garantia", "Ninguna ruta asegura ingresos, patrocinios ni contrataciones profesionales.")


def page_graph(facade: GamePathFacade):
    topline("LABORATORIO DE GRAFOS")
    hero("NON-LINEAR DATA STRUCTURES // LAB", "ENTIENDE EL<br><em>ALGORITMO.</em>",
         "Visualiza el grafo del backend, explora recorridos BFS / DFS y analiza el camino de menor costo con Dijkstra.",compact=True)
    nodes=facade.graph.node_count
    edges=facade.graph.edge_count
    c1,c2,c3=st.columns(3)
    with c1: metric(nodes,"Nodos del grafo","Definidos en training_graph.json")
    with c2: metric(edges,"Aristas dirigidas","Con pesos en horas","red")
    with c3: metric("3","Algoritmos","BFS / DFS / Dijkstra","green")
    heading("Grafo completo", "LOS PESOS ESTAN EN LAS ARISTAS")
    graph_diagram(facade.graph)
    a,b=st.columns([.9,1.1],gap="large")
    with a:
        heading("Recorridos de exploracion", "BFS VS DFS")
        includes=st.checkbox("Incluir aristas de oportunidades en simulacion",value=False)
        traversals=facade.graph_traversals(include_opportunities=includes)
        selected=st.radio("Algoritmo",["BFS","DFS"],horizontal=True)
        details_box(f"Orden {selected}",[(f"Paso {i+1:02d}",node) for i,node in enumerate(traversals[selected])])
    with b:
        heading("Calculo de ruta", "DIJKSTRA")
        st.markdown('''<div class="gp-panel"><div class="gp-eyebrow">PESO // HORAS DE PREPARACION</div><div class="gp-panel-title">RUTA MINIMA</div><div class="gp-muted">Dijkstra calcula el camino con el menor costo acumulado, respetando requisitos de ingreso al grafo y estados del jugador.</div></div>''',unsafe_allow_html=True)
        admitted=[s for s in facade.list_summaries() if s.decision=="approved"]
        if admitted:
            selected_id=st.selectbox("Ruta de aspirante admitido",options=[s.applicant.applicant_id for s in admitted],format_func=lambda i:next(s.applicant.game_name for s in admitted if s.applicant.applicant_id==i))
            try:
                plan=facade.training_plan(selected_id)
                route_cards(plan.nodes,plan.activities,facade.graph)
                st.metric("Costo restante de preparacion",f"{plan.estimated_hours:g} h")
            except (ValueError,PermissionError) as exc:st.warning(str(exc))
        else:
            insight("Sin rutas de jugadores aun", "Registra un VOD, apruebalo por un reclutador y el sistema calculara la ruta real desde el progreso guardado.")
    st.caption("BFS y DFS de esta seccion son una simulacion educativa del grafo configurado; no cambian el estado ni otorgan acceso a oportunidades.")


def page_config(facade: GamePathFacade):
    topline("CONFIGURACION", "MODO ACADEMICO / LOCAL")
    hero("SYSTEM OPERATIONS // SETTINGS", "BASE DE<br><em>OPERACIONES.</em>",
         "Prepara la demostracion, revisa el almacenamiento y exporta la informacion del proyecto.",compact=True)
    st.warning("PROTOTIPO LOCAL: no dispone de login ni autenticacion real. No publiques esta interfaz en Internet con datos personales o VOD reales sin incorporar seguridad, permisos y politicas de privacidad.")
    col1,col2=st.columns([1,1],gap="large")
    with col1:
        heading("Puesta en marcha", "DEMO CONTROLADA")
        details_box("Estado de los servicios",[
            ("Base de datos", str(facade.db_path)),
            ("Motor", "SQLite"),
            ("Arbol", "profile_tree.json"),
            ("Grafo", "training_graph.json"),
            ("Aspirantes", str(facade.counts()["total"])),
        ])
        if st.button("HABILITAR RECLUTADOR LOCAL",use_container_width=True):
            facade.activate_local_reviewer()
            st.success("Reclutador local habilitado exclusivamente para pruebas.")
            st.rerun()
        if st.button("CARGAR DATOS DE DEMOSTRACION",type="primary",use_container_width=True):
            try:
                added=facade.seed_demo()
                st.success(f"Escenario demo listo. Aspirantes nuevos: {added}.")
                st.rerun()
            except (ValueError,PermissionError,sqlite3.IntegrityError) as exc:st.error(str(exc))
        st.caption("Esta accion inserta datos ficticios en la base de datos configurada. Es idempotente para los seis IDs de prueba. No se ejecuta automaticamente.")
    with col2:
        heading("Herramientas", "OPERACION Y EXPORTACION")
        st.download_button("DESCARGAR ASPIRANTES CSV",data=facade.export_csv(),file_name="gamepath_roster.csv",mime="text/csv",use_container_width=True)
        details_box("Reclutadores configurados", [
            (r["display_name"], "ACTIVO" if r["is_active"] else "INACTIVO") for r in facade.list_reviewers()
        ] or [("Sin reclutadores", "Habilita uno para la demo")])
        insight("Persistencia real", "Cada registro, revision, entrenamiento y reevaluacion se guarda en SQLite a traves de los servicios del backend.")
    heading("Flujo funcional implementado", "EXTREMO A EXTREMO")
    st.markdown('''<div class="gp-route">
        <div class="gp-route-tile"><div class="n">01 /</div><div class="title">Registro</div><div class="desc">Perfil del aspirante</div></div>
        <div class="gp-route-tile"><div class="n">02 /</div><div class="title">Preseleccion</div><div class="desc">Arbol binario</div></div>
        <div class="gp-route-tile"><div class="n">03 /</div><div class="title">Evaluacion VOD</div><div class="desc">Decision humana</div></div>
        <div class="gp-route-tile"><div class="n">04 /</div><div class="title">Entrenamiento</div><div class="desc">Grafo y Dijkstra</div></div>
        <div class="gp-route-tile"><div class="n">05 /</div><div class="title">Reevaluacion</div><div class="desc">Revision final</div></div>
        <div class="gp-route-tile"><div class="n">06 /</div><div class="title">Oportunidades</div><div class="desc">3 caminos posibles</div></div>
    </div>''',unsafe_allow_html=True)
    st.markdown("El frontend incluye registro, preseleccion, carga/referencia de VOD, evaluacion humana, rutas calculadas, progreso certificado, reevaluacion, oportunidades y laboratorio de algoritmos.")


def main():
    install_theme()
    try:
        facade=get_facade()
    except Exception as exc:
        st.error("No fue posible inicializar el backend: " + str(exc))
        st.stop()
    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "Centro de mando"
    if st.session_state["nav_page"] not in PAGES:
        st.session_state["nav_page"] = PAGES[0]
    if "_pending_nav_radio" in st.session_state:
        st.session_state["nav_radio"] = st.session_state.pop("_pending_nav_radio")
    with st.sidebar:
        sidebar_brand()
        sidebar_divider("SISTEMA DE RECLUTAMIENTO")
        selected=st.radio("Navegacion",options=PAGES,index=PAGES.index(st.session_state["nav_page"]),key="nav_radio",label_visibility="collapsed")
        if selected != st.session_state["nav_page"]:
            st.session_state["nav_page"] = selected
        sidebar_footer()

    # Navegacion alternativa persistente: no depende del boton de expandir.
    with st.popover("☰ MENÚ", use_container_width=False):
        st.caption("NAVEGACIÓN RÁPIDA // GAMEPATH")
        quick_page = st.selectbox(
            "Ir a sección",
            options=PAGES,
            index=PAGES.index(st.session_state["nav_page"]),
            key="quick_nav_destination",
        )
        if st.button("ABRIR SECCIÓN", key="quick_nav_open", type="primary", use_container_width=True):
            go_to(quick_page)

    page=st.session_state["nav_page"]
    pages={
        "Centro de mando":page_dashboard,
        "Aspirantes":page_applicants,
        "Nuevo aspirante":page_register,
        "Perfil del jugador":page_profile,
        "Preseleccion":page_preselection,
        "Evaluacion de VOD":page_review,
        "Entrenamiento":page_training,
        "Reevaluacion":page_reevaluation,
        "Oportunidades":page_opportunities,
        "Laboratorio de grafos":page_graph,
        "Configuracion":page_config,
    }
    try:
        pages[page](facade)
    except Exception as exc:
        st.error(f"Ocurrio un error al cargar {page}: {exc}")
        st.caption("Consulta la terminal para revisar el error del backend. Los datos no fueron modificados por esta vista.")
        raise
    footer()


if __name__ == "__main__":
    main()
