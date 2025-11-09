
# Gradio UI — Orquestador (oscuro legible + descarga PDF)
import json, re, time, httpx, gradio as gr
from pathlib import Path

API_BASE = "http://localhost:8000"
gr.set_static_paths(paths=[str((Path(__file__).resolve().parent.parent / "exports").resolve())])

def _get_json(r):
    try: return r.json()
    except Exception: return {"text": r.text}

async def call_api(path: str, method: str = "GET", json_body=None):
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await (client.get(API_BASE + path) if method=="GET" else client.post(API_BASE + path, json=json_body))
    try: data = r.json()
    except Exception: data = {"text": r.text}
    return r.status_code, data

async def orchestrate(user_msg, show_drivers=True, include_citations=True):
    msg = (user_msg or "").strip(); t0 = time.time()
    if msg.lower()=="/health":
        s1,h = await call_api("/health"); s2,e = await call_api("/endpoints")
        return (f"**/health ({s1})**\n```json\n{json.dumps(h,indent=2,ensure_ascii=False)}\n```\n\n"
                f"**/endpoints ({s2})**\n```json\n{json.dumps(e,indent=2,ensure_ascii=False)}\n```", [])
    if msg.lower().startswith("/kb "):
        q = msg[4:].strip(); s,res = await call_api(f"/kb/search?q={q}&k=5")
        if isinstance(res, list) and res:
            return "\n".join([f"- **{it.get('title','')}** — {it.get('snippet','')}" for it in res]), []
        return "KB sin resultados", []
    s_ex, ex = await call_api("/extract", method="POST", json_body={"text": msg})
    if s_ex!=200 or "input" not in ex:
        ex = {"input":{"sex":"M","age":40,"height_cm":175,"weight_kg":82,"waist_cm":94,
                       "sbp":128,"dbp":82,"sleep_hours":6.5,"days_mvpa_week":3,
                       "smokes_cig_day":0,"fruit_veg_portions_day":3.0,"income_poverty_ratio":2.0}}
    s_pr, pr = await call_api("/predict", method="POST", json_body=ex["input"])
    score = pr.get("score"); drivers = pr.get("drivers") or []
    m = re.search(r"(objetivo|meta)\s*:\s*(.+)$", msg, flags=re.I); goal = m.group(2).strip() if m else msg
    s_co, co = await call_api(f"/coach_llm?goal={goal}", method="POST", json_body=ex["input"])
    plan = co.get("plan",[]) if isinstance(co,dict) else []; citas = co.get("citas",[]) if isinstance(co,dict) else []
    disclaimer = co.get("disclaimer","No es diagnóstico médico.")
    md = []
    md.append("## Predicción y Plan")
    md.append(f"**Score de riesgo**: { (f'{score*100:.1f}%' if isinstance(score,(int,float)) else 'N/D') }")
    if show_drivers and drivers: md.append("**Drivers del modelo**: " + ", ".join(drivers[:8]))
    if plan:
        md.append("\n### Plan sugerido (4–12 semanas)")
        for p in plan[:10]: md.append("- " + p)
    if include_citations and citas:
        md.append("\n**Citas KB:**"); [md.append("- " + c) for c in citas]
    md.append(f"\n> _{disclaimer}_")
    md.append("\n<details><summary>Entrada interpretada (/extract)</summary>\n\n" +
              "```json\n" + json.dumps(ex["input"], indent=2, ensure_ascii=False) + "\n```\n</details>")
    if s_pr==200:
        md.append("<details><summary>Respuesta /predict</summary>\n\n" +
                  "```json\n" + json.dumps(pr, indent=2, ensure_ascii=False) + "\n```\n</details>")
    md.append(f"\n⏱️ {time.time()-t0:.2f}s")
    return "\n".join(md), plan

async def do_turn(user_msg, history, show_drivers, include_citations):
    if not (user_msg or '').strip(): return history, []
    reply, plan = await orchestrate(user_msg, show_drivers, include_citations)
    return (history or []) + [[user_msg, reply]], plan

async def export_pdf(plan: list):
    if not plan: return gr.update(value=None)
    s,res = await call_api("/report/pdf", method="POST",
                           json_body={"plan":plan,"header":"Plan personalizado","footer":"No es diagnóstico médico."})
    if s==200 and isinstance(res,dict) and res.get("path"):
        return gr.update(value=res["path"], visible=True)
    return gr.update(value=None)

with gr.Blocks(theme=gr.themes.Base(), fill_height=True, css="body{background:#111;color:#eee}") as demo:
    gr.Markdown("## Coach Preventivo — Orquestador (RAG + ML)")
    with gr.Row():
        with gr.Column(scale=1, min_width=280):
            status_btn = gr.Button("↻ Estado API", variant="secondary")
            status_md  = gr.Markdown("Pulsa **Estado API** para ver /health y /endpoints.")
            with gr.Accordion("🔎 KB", open=False):
                kb_q  = gr.Textbox(label="Consulta", placeholder="ej: sueño y ejercicio")
                kb_go = gr.Button("Buscar")
                kb_md = gr.Markdown("_sin búsqueda_")
            with gr.Accordion("⚙️ Opciones", open=True):
                show_drivers = gr.Checkbox(value=True, label="Mostrar drivers del modelo")
                include_citations = gr.Checkbox(value=True, label="Incluir citas de KB")
                gr.Markdown("Comandos: `/health`, `/endpoints`, `/kb <tema>`")
            with gr.Accordion("🧪 Ejemplos", open=False):
                ex1 = gr.Button("hombre, 42 años, 1.75m, 86kg, cintura 92cm, presión 128/82, duermo 6.5h, objetivo: bajar riesgo cardiometabólico")
                ex2 = gr.Button("mujer, 35 años, 1.62m, 70kg, cintura 85cm, no fumo, ejercicio 2 días/sem, objetivo: dormir mejor")
                ex3 = gr.Button("/kb sueño y actividad física")
        with gr.Column(scale=3):
            chat = gr.Chatbot(label="Chat", height=520, layout="bubble", show_copy_button=True)
            with gr.Row():
                msg = gr.Textbox(label="Mensaje", placeholder="Escribe aquí…", scale=8)
                send = gr.Button("Enviar", variant="primary", scale=1)
                clear = gr.Button("Limpiar", variant="secondary", scale=1)
            with gr.Row():
                plan_state = gr.State([])
                gen_pdf = gr.Button("📄 Generar PDF del plan", variant="secondary")
                dl_pdf  = gr.DownloadButton("⬇️ Descargar PDF", visible=True)
    async def on_send(m, hist, sd, ic, st):
        new_hist, plan = await do_turn(m, hist, sd, ic)
        return new_hist, gr.update(value=""), plan
    send.click(on_send, inputs=[msg, chat, show_drivers, include_citations, plan_state],
               outputs=[chat, msg, plan_state])
    msg.submit(on_send, inputs=[msg, chat, show_drivers, include_citations, plan_state],
               outputs=[chat, msg, plan_state])
    clear.click(lambda: ([], []), inputs=None, outputs=[chat, plan_state])
    async def on_health():
        s1,h = await call_api("/health"); s2,e = await call_api("/endpoints")
        return f"**/health ({s1})**\n```json\n{json.dumps(h,indent=2,ensure_ascii=False)}\n```\n\n" + \
               f"**/endpoints ({s2})**\n```json\n{json.dumps(e,indent=2,ensure_ascii=False)}\n```"
    async def on_kb(q):
        if not (q or '').strip(): return "_ingresa una consulta_"
        s,res = await call_api(f"/kb/search?q={q}&k=5")
        if isinstance(res,list) and res:
            return "\n".join([f"- **{it.get('title','')}** — {it.get('snippet','')}" for it in res])
        return "_sin resultados_"
    async def on_export(plan): return await export_pdf(plan)
    status_btn.click(on_health, inputs=None, outputs=[status_md])
    kb_go.click(on_kb, inputs=[kb_q], outputs=[kb_md])
    ex1.click(on_send, inputs=[gr.State("hombre, 42 años, 1.75m, 86kg, cintura 92cm, presión 128/82, duermo 6.5h, objetivo: bajar riesgo cardiometabólico"),
                               chat, show_drivers, include_citations, plan_state],
              outputs=[chat, msg, plan_state])
    ex2.click(on_send, inputs=[gr.State("mujer, 35 años, 1.62m, 70kg, cintura 85cm, no fumo, ejercicio 2 días/sem, objetivo: dormir mejor"),
                               chat, show_drivers, include_citations, plan_state],
              outputs=[chat, msg, plan_state])
    ex3.click(on_send, inputs=[gr.State("/kb sueño y actividad física"),
                               chat, show_drivers, include_citations, plan_state],
              outputs=[chat, msg, plan_state])
    gen_pdf.click(on_export, inputs=[plan_state], outputs=[dl_pdf])

if __name__ == "__main__":
    demo.queue(concurrency_count=16).launch(server_name="0.0.0.0", server_port=7860)
