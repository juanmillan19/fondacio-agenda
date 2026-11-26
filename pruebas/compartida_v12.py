"""Pruebas de la agenda compartida (v1.2) con dos equipos a la vez y un Firebase simulado.

Antes, en otra terminal: python pruebas/servidor_prueba.py (sirve el proyecto y un Firebase simulado en http://localhost:8001).
El Firebase simulado aplica las mismas reglas de acceso que firestore.rules.
Uso: python pruebas/compartida_v12.py
"""
import asyncio, json, urllib.request
from playwright.async_api import async_playwright

URL = "http://localhost:8001/fondacio.html?sinTour"
DB = "http://localhost:8001/__db"
res = []

def ok(nombre, cond, extra=""):
    res.append((nombre, bool(cond)))
    print(("OK   " if cond else "FALLA") + " " + nombre + (" · " + str(extra) if extra and not cond else ""))

def db():
    return json.loads(urllib.request.urlopen(DB).read())

async def esperar(pg, expr, ms=4000):
    try:
        await pg.wait_for_function(expr, timeout=ms); return True
    except Exception:
        return False

async def equipo(b, correo):
    ctx = await b.new_context(viewport={"width": 1280, "height": 860})
    await ctx.add_init_script(f"window.FB_BASE='/pruebas/fbmock/';window.__mockLogin={json.dumps(correo)};window.confirm=()=>true;")
    pg = await ctx.new_page(); pg.errores = []
    pg.on("pageerror", lambda e: pg.errores.append(str(e)))
    await pg.goto(URL); await pg.wait_for_timeout(600)
    return pg

async def main():
    urllib.request.urlopen(DB + "/reset").read()
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])

        # --- Equipo A: Carlos (coordinación) ---
        A = await equipo(b, "carpo0622@gmail.com")
        ok("A: sin cuenta, el botón invita a compartir", "compartir con el equipo" in await A.inner_text("#bNube"))
        await A.evaluate("""()=>{S.ejemplo=false;S.eventos=[{id:'e1',titulo:'Taller de IA',eje:'form',fecha:'2026-12-05',ini:'09:00',fin:'11:00',lugar:'Salón comunal'}];
            S.pend=[];S.contactos=['ana@gmail.com'];save();render()}""")
        await A.click("#bNube"); await A.click("#nEntrar")
        ok("A: entra y queda compartida", await esperar(A, "nube.estado==='ok'&&nube.listo.eventos&&nube.listo.pend"))
        await A.wait_for_timeout(500)
        d = db()
        ok("Nube: se creó la agenda de la fundación con Carlos como coordinación",
           d.get("espacios/fondacio", {}).get("admins") == ["carpo0622@gmail.com"])
        ok("Nube: la actividad local de Carlos se subió", "espacios/fondacio/eventos/e1" in d)
        ok("Nube: los correos guardados se subieron", d.get("espacios/fondacio/datos/contactos", {}).get("lista") == ["ana@gmail.com"])
        ok("A: el botón dice Compartida", "Compartida" in await A.inner_text("#bNube"))

        # Carlos da acceso a Juan
        await A.fill("#nCorreo", "Juan@Gmail.com"); await A.click("#nAdd")
        ok("A: agrega a juan@gmail.com (en minúsculas)", await esperar(A, "nube.miembros.includes('juan@gmail.com')"))
        ok("A: Juan aparece en la lista de integrantes", await esperar(A, "document.querySelector('.miembros').innerText.includes('juan@gmail.com')"))
        await A.click("#x")

        # --- Equipo B: alguien sin acceso ---
        B = await equipo(b, "otra@gmail.com")
        ejemplosB = await B.evaluate("S.eventos.length")
        await B.click("#bNube"); await B.click("#nEntrar")
        ok("B: un correo sin permiso queda sin acceso", await esperar(B, "nube.estado==='sinAcceso'"))
        ok("B: el diálogo explica que pida acceso", await esperar(B, "document.querySelector('#fNube').innerText.includes('todavía no tiene acceso')"))
        ok("Nube: el correo sin permiso no pudo escribir nada", len([k for k in db() if k.startswith("espacios/fondacio/eventos/")]) == 1)
        # entra con la cuenta correcta
        await B.evaluate("window.__mockLogin='juan@gmail.com'"); await B.click("#nOtra")
        ok("B: Juan entra a la agenda compartida", await esperar(B, "nube.estado==='ok'&&nube.listo.eventos&&nube.listo.pend&&nube.listo.contactos"))
        await B.wait_for_timeout(400)
        ok("B: los datos de ejemplo de Juan no se subieron", len([k for k in db() if k.startswith("espacios/fondacio/eventos/")]) == 1, ejemplosB)
        ok("B: Juan ve la misma actividad que Carlos", await B.evaluate("S.eventos.length===1&&S.eventos[0].titulo==='Taller de IA'"))
        ok("B: Juan no ve controles de coordinación", await B.evaluate("!document.querySelector('#nAdd')"))
        await B.click("#x")

        # --- cambios en tiempo real ---
        await B.evaluate("""()=>{S.eventos.push({id:'e2',titulo:'Feria de ropa',eje:'eco',fecha:'2026-12-06',ini:'10:00',fin:'14:00',lugar:'Parque'});save();render()}""")
        ok("A: ve al instante la actividad que creó Juan", await esperar(A, "S.eventos.some(e=>e.id==='e2')"))
        ok("A: el calendario se volvió a dibujar", await esperar(A, "document.body.innerText.includes('Feria de ropa')||S.eventos.length===2"))
        await A.evaluate("()=>{const e=S.eventos.find(x=>x.id==='e2');e.titulo='Feria de ropa y juguetes';save();render()}")
        ok("B: ve la edición de Carlos", await esperar(B, "S.eventos.some(e=>e.titulo==='Feria de ropa y juguetes')"))
        ok("Nube: guarda quién hizo el último cambio", db()["espacios/fondacio/eventos/e2"].get("_por") == "carpo0622@gmail.com")
        # un formulario abierto en B sigue apuntando al mismo objeto después de una actualización remota
        await B.evaluate("window.__ref=S.eventos.find(x=>x.id==='e1')")
        await A.evaluate("()=>{S.eventos.find(x=>x.id==='e1').lugar='Casa cultural';save()}")
        await esperar(B, "S.eventos.find(x=>x.id==='e1').lugar==='Casa cultural'")
        ok("B: un formulario abierto no pierde la actividad al llegar cambios", await B.evaluate("window.__ref===S.eventos.find(x=>x.id==='e1')&&window.__ref.lugar==='Casa cultural'"))
        await B.evaluate("()=>{S.eventos=S.eventos.filter(x=>x.id!=='e2');save();render()}")
        ok("A: ve que Juan borró una actividad", await esperar(A, "!S.eventos.some(e=>e.id==='e2')"))
        ok("Nube: la actividad borrada ya no está", "espacios/fondacio/eventos/e2" not in db())

        # pendientes compartidos
        await A.evaluate("""()=>{S.pend.unshift({id:'p1',estado:'pendiente',recibido:new Date().toISOString(),texto:'Hola, los invitamos a la reunión de la JAC el sábado 3 pm',de:'Junta',org:'JAC',tipo:'reunion',titulo:'Reunión JAC',fecha:'2026-12-12',ini:'15:00'});save();renderPend()}""")
        ok("B: el pendiente que llegó a Carlos también aparece para Juan", await esperar(B, "S.pend.some(p=>p.id==='p1')"))
        ok("B: el número de pendientes se actualiza", await esperar(B, "document.querySelector('#nPend').textContent==='1'"))
        await B.evaluate("()=>{const p=S.pend.find(x=>x.id==='p1');p.estado='rechazada';save();render()}")
        ok("A: ve que Juan ya respondió el pendiente", await esperar(A, "S.pend.find(p=>p.id==='p1').estado==='rechazada'"))

        # correos de invitados compartidos
        await B.evaluate("()=>{S.contactos.push('maria@gmail.com');save()}")
        ok("A: recibe el correo que guardó Juan", await esperar(A, "S.contactos.includes('maria@gmail.com')"))

        # sin internet
        await B.evaluate("()=>{window.__mockOffline=true;Object.defineProperty(navigator,'onLine',{get:()=>false,configurable:true});dispatchEvent(new Event('offline'))}")
        ok("B: el botón avisa que está sin internet", "sin internet" in await B.inner_text("#bNube"))
        await B.evaluate("""()=>{S.eventos.push({id:'e3',titulo:'Visita a familias',eje:'com',fecha:'2026-12-08',ini:'08:00',lugar:'Barrio'});save();render()}""")
        await A.wait_for_timeout(900)
        ok("A: lo hecho sin internet aún no llega", not await A.evaluate("S.eventos.some(e=>e.id==='e3')"))
        ok("B: Juan sigue viendo su actividad sin internet", await B.evaluate("S.eventos.some(e=>e.id==='e3')"))
        await B.evaluate("async()=>{window.__mockOffline=false;Object.defineProperty(navigator,'onLine',{get:()=>true,configurable:true});dispatchEvent(new Event('online'));await window.__mockFlush()}")
        ok("A: al volver el internet, llega lo que Juan hizo sin conexión", await esperar(A, "S.eventos.some(e=>e.id==='e3')"))
        ok("B: el botón vuelve a Compartida", await esperar(B, "document.querySelector('#nubeEst').textContent.startsWith('Compartida · ')&&!document.querySelector('#nubeEst').textContent.includes('internet')"))

        # recargar: entra sola, sin pedir cuenta otra vez, y no duplica nada
        await A.reload(); await A.wait_for_timeout(300)
        ok("A: al recargar entra sola", await esperar(A, "typeof nube!=='undefined'&&nube.estado==='ok'&&nube.listo.eventos"))
        await A.wait_for_timeout(600)
        ok("A: al recargar no se duplica nada", await A.evaluate("S.eventos.length===2&&new Set(S.eventos.map(e=>e.id)).size===2"), await A.evaluate("S.eventos.map(e=>e.id)"))
        ok("Nube: sigue con 2 actividades", len([k for k in db() if k.startswith("espacios/fondacio/eventos/")]) == 2, [k for k in db() if "eventos/" in k])

        # Juan no puede cambiar quién tiene acceso
        r = await B.evaluate("async()=>{try{await nube.fb.updateDoc(nube.ref,{miembros:nube.fb.arrayUnion('intruso@gmail.com')});return 'paso'}catch(e){return e.code}}")
        ok("Reglas: una integrante sin coordinación no puede dar acceso", r == "permission-denied", r)

        # Carlos le quita el acceso a Juan
        await A.click("#bNube")
        await A.click("[data-quitar='juan@gmail.com']")
        ok("B: al quitarle el acceso, Juan queda sin acceso", await esperar(B, "nube.estado==='sinAcceso'"))
        await A.click("#x")
        n_antes = len([k for k in db() if k.startswith("espacios/fondacio/eventos/")])
        await B.evaluate("()=>{S.eventos.push({id:'e9',titulo:'No debería subir',eje:'eq',fecha:'2026-12-20',ini:'08:00'});save()}")
        await B.wait_for_timeout(600)
        ok("Nube: Juan ya no puede escribir", len([k for k in db() if k.startswith("espacios/fondacio/eventos/")]) == n_antes)

        # salir de la cuenta
        await A.click("#bNube"); await A.click("#nSalir")
        ok("A: al salir vuelve a la agenda en este equipo", await esperar(A, "nube.estado==='fuera'"))
        ok("A: conserva la copia de lo que veía", await A.evaluate("S.eventos.length===2"), await A.evaluate("S.eventos.map(e=>e.id)"))

        ok("Sin errores de JavaScript en A", not A.errores, A.errores)
        ok("Sin errores de JavaScript en B", not B.errores, B.errores)
        await b.close()
    n = sum(1 for _, v in res if v)
    print(f"\n{n}/{len(res)} pruebas aprobadas")

asyncio.run(main())
