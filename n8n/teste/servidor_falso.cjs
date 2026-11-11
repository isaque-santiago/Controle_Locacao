// Servidor falso para testar o fluxo do n8n: imita o Supabase (login do usuário de serviço e as RPCs rpc_whatsapp_*) e a Evolution
// (estado da instância, conferência do número e envio de texto), na mesma porta. Registra cada chamada no arquivo de log (JSON por linha).
// O cenário (o que cada endpoint responde) é trocado por POST /_cenario. Uso: node servidor_falso.cjs <porta> <arquivo-de-log>.
// Credenciais fictícias: apikey anônima `anon-teste`, usuário `robo@exemplo.com`/`senha-robo`, apikey da Evolution `evo-teste`.
const http = require('http'); const fs = require('fs');
const LOG = process.argv[3]; const PORTA = Number(process.argv[2]);
let cenario = { estado: 'open', reservar: [], numeros: {}, envio: {}, reservarStatus: 200, loginStatus: 200 };
function registrar(o) { fs.appendFileSync(LOG, JSON.stringify(o) + '\n'); }
http.createServer((req, res) => {
  let corpo = ''; req.on('data', c => corpo += c);
  req.on('end', () => {
    let json = null; try { json = corpo ? JSON.parse(corpo) : null; } catch (_) {}
    const u = new URL(req.url, 'http://x'); const caminho = u.pathname;
    const h = req.headers;
    const responder = (status, obj) => { res.writeHead(status, { 'content-type': 'application/json' }); res.end(obj === undefined ? '' : JSON.stringify(obj)); };
    if (caminho === '/_cenario') { cenario = { ...cenario, ...json }; return responder(200, { ok: true }); }
    registrar({ metodo: req.method, caminho, apikey: h['apikey'], auth: h['authorization'], corpo: json });
    if (caminho === '/auth/v1/token') {
      if (json && json.email === 'robo@exemplo.com' && json.password === 'senha-robo' && h['apikey'] === 'anon-teste') return responder(cenario.loginStatus, { access_token: 'tok-servico' });
      return responder(400, { error: 'invalid_credentials' });
    }
    if (caminho.startsWith('/rest/v1/rpc/')) {
      if (h['authorization'] !== 'Bearer tok-servico' || h['apikey'] !== 'anon-teste') return responder(401, { message: 'JWT inválido' });
      const nome = caminho.split('/').pop();
      if (nome === 'rpc_whatsapp_reservar') return responder(cenario.reservarStatus, cenario.reservar);
      if (nome === 'rpc_whatsapp_registrar_rodada') return responder(204);
      if (nome === 'rpc_whatsapp_registrar_resultado') return responder(200, { status: json.p_resultado, tentativas: 1 });
      return responder(404, { message: 'RPC desconhecida' });
    }
    if (h['apikey'] !== 'evo-teste') return responder(401, { message: 'Unauthorized' });
    if (caminho.startsWith('/instance/connectionState/')) {
      if (cenario.estado === 'http500') return responder(500, { message: 'erro' });
      if (cenario.estado === 'http401') return responder(401, { message: 'Unauthorized' });
      return responder(200, { instance: { instanceName: 'locacao', state: cenario.estado } });
    }
    if (caminho.startsWith('/chat/whatsappNumbers/')) {
      const n = json.numbers[0]; const c = cenario.numeros[n] || { status: 200, exists: true };
      if (c.status !== 200) return responder(c.status, { message: 'erro' });
      return responder(200, [{ exists: c.exists, number: n }]);
    }
    if (caminho.startsWith('/message/sendText/')) {
      const n = json.number || (json.number); const c = cenario.envio[n] || { status: 201 };
      if (c.status >= 400) return responder(c.status, { message: 'erro' });
      return responder(201, { key: { id: 'EVO-' + n.slice(-4) } });
    }
    responder(404, { message: 'não encontrado' });
  });
}).listen(PORTA, '127.0.0.1', () => console.log('mock ouvindo em', PORTA));
