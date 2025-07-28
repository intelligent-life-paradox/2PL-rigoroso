import networkx as nx
import re
from collections import defaultdict, deque

class Escalonador2PLMGU:

    def __init__(self):
        self.hierarquia = {
            'DB': ['TB1', 'TB2'],
            'TB1': ['TB1.P1', 'TB1.P2'], 'TB2': ['TB2.P1', 'TB2.P2'],
            'TB1.P1': ['TB1.P1.TU1', 'TB1.P1.TU2'], 'TB1.P2': ['TB1.P2.TU1', 'TB1.P2.TU2'],
            'TB2.P1': ['TB2.P1.TU1', 'TB2.P1.TU2'], 'TB2.P2': ['TB2.P2.TU1', 'TB2.P2.TU2']
        }
        self.mapa_pais = {filho: pai for pai, filhos in self.hierarquia.items() for filho in filhos}
        self.mapa_pais['DB'] = None
        self.bloqueios = defaultdict(dict)
        self.fila_espera = deque()
        self.historico = []
        self.transacoes_abortadas = set()
        self.transacoes_commitadas = set()
        self.grafo_espera = nx.DiGraph()
        self.operacoes_pendentes = {}

    modos_bloqueio = {'IS': 0, 'IX': 1, 'S': 2, 'X': 3, 'U': 4}
    matriz_compatibilidade = {
        'IS': [True,  True,  True,  False, True],
        'IX': [True,  True,  False, False, False],
        'S':  [True,  False, True,  False, True],
        'X':  [False, False, False, False, False],
        'U':  [True,  False, True,  False, False]
    }

    def _e_compativel(self, modo_requisitado, bloqueios_existentes):
        for modo_existente in bloqueios_existentes.values():
            if not self.matriz_compatibilidade[modo_requisitado][self.modos_bloqueio[modo_existente]]:
                return False
        return True

    def _obter_pai(self, item):
        return self.mapa_pais.get(item)

    def _obter_ancestrais(self, item):
        ancestrais, pai = [], self._obter_pai(item)
        while pai:
            ancestrais.insert(0, pai)
            pai = self._obter_pai(pai)
        return ancestrais

    def _solicitar_bloqueio(self, id_transacao, item, modo):
        if id_transacao in self.transacoes_abortadas or id_transacao in self.transacoes_commitadas:
            return False

        bloqueio_atual = self.bloqueios[item].get(id_transacao)
        if bloqueio_atual:
            if (bloqueio_atual == modo or
                bloqueio_atual == 'X' or
                (bloqueio_atual == 'IX' and modo in ['IS', 'S']) or
                (bloqueio_atual == 'S' and modo == 'IS') or
                (bloqueio_atual == 'U' and modo == 'S')):
                return True

            caminho_de_upgrade_valido = (bloqueio_atual == 'IS' and modo in ['IX', 'S', 'U', 'X']) or \
                                      (bloqueio_atual == 'S' and modo in ['U', 'X']) or \
                                      (bloqueio_atual == 'IX' and modo == 'X') or \
                                      (bloqueio_atual == 'U' and modo == 'X')

            if caminho_de_upgrade_valido:
                if modo in ['S', 'U', 'X']:
                    intencao_requerida = 'IX' if modo in ['X', 'U'] else 'IS'
                    for ancestral in self._obter_ancestrais(item):
                        if not self._solicitar_bloqueio(id_transacao, ancestral, intencao_requerida):
                            return False

                outros_bloqueios = {id_t: m for id_t, m in self.bloqueios[item].items() if id_t != id_transacao}
                if self._e_compativel(modo, outros_bloqueios):
                    self.historico.append(f"upgrade{id_transacao}({item}): {bloqueio_atual}->{modo}")
                    self.bloqueios[item][id_transacao] = modo
                    return True
                else:
                    return self._adicionar_espera(id_transacao, (item, modo), list(outros_bloqueios.keys()))

            return self._adicionar_espera(id_transacao, (item, modo), list(self.bloqueios[item].keys()))

        if modo in ['S', 'U', 'X']:
            intencao_requerida = 'IX' if modo in ['X', 'U'] else 'IS'
            for ancestral in self._obter_ancestrais(item):
                if not self._solicitar_bloqueio(id_transacao, ancestral, intencao_requerida):
                    return False

        if not self._e_compativel(modo, self.bloqueios[item]):
              return self._adicionar_espera(id_transacao, (item, modo), list(self.bloqueios[item].keys()))

        self.bloqueios[item][id_transacao] = modo
        self.historico.append(f"{modo.lower()}{id_transacao}({item})")
        return True

    def _ler(self, id_transacao, item):
        if self._solicitar_bloqueio(id_transacao, item, 'S'):
            self.historico.append(f"r{id_transacao}({item})")
            return True
        return False

    def _atualizar(self, id_transacao, item):
        if self._solicitar_bloqueio(id_transacao, item, 'U'):
            self.historico.append(f"u{id_transacao}({item})")
            return True
        return False

    def _escrever(self, id_transacao, item):
        if self._solicitar_bloqueio(id_transacao, item, 'X'):
            self.historico.append(f"w{id_transacao}({item})")
            return True
        return False

    def _efetivar_commit(self, id_transacao):
        if any(op[0] == id_transacao for op in self.fila_espera):
            self.historico.append(f"Commit c{id_transacao} recebido, mas T{id_transacao} está em espera. Commit pendente.")
            self.operacoes_pendentes[id_transacao] = 'c'
            return

        if id_transacao in self.transacoes_abortadas or id_transacao in self.transacoes_commitadas:
            return

        self.transacoes_commitadas.add(id_transacao)
        self.historico.append(f"c{id_transacao}")
        self._liberar_recursos(id_transacao)
        self._processar_fila_espera()

    def _abortar(self, id_transacao, motivo=""):
        if id_transacao in self.transacoes_abortadas or id_transacao in self.transacoes_commitadas:
            return

        self.transacoes_abortadas.add(id_transacao)
        self.historico.append(f"abort{id_transacao}{' (' + motivo + ')' if motivo else ''}")
        self._liberar_recursos(id_transacao)
        self.fila_espera = deque([op for op in self.fila_espera if op[0] != id_transacao])
        if id_transacao in self.operacoes_pendentes:
            del self.operacoes_pendentes[id_transacao]
        self._processar_fila_espera()

    def _liberar_recursos(self, id_transacao):
        itens_para_desbloquear = [item for item, lcks in self.bloqueios.items() if id_transacao in lcks]
        for item in sorted(itens_para_desbloquear, key=lambda x: -len(x)):
            if id_transacao in self.bloqueios[item]:
                modo = self.bloqueios[item].pop(id_transacao)
                self.historico.append(f"unlock{modo.lower()}{id_transacao}({item})")
                if not self.bloqueios[item]:
                    del self.bloqueios[item]
        if self.grafo_espera.has_node(id_transacao):
            self.grafo_espera.remove_node(id_transacao)

    def _adicionar_espera(self, id_transacao, operacao, ids_aguardados):
        if (id_transacao, operacao) not in self.fila_espera:
            self.fila_espera.append((id_transacao, operacao))

        item, modo = operacao
        ids_aguardados_limpo = sorted([id_t for id_t in ids_aguardados if id_t != id_transacao])

        if not ids_aguardados_limpo:
            return False

        self.historico.append(f"T{id_transacao} espera por {modo} em {item} (bloqueado por T{ids_aguardados_limpo})")
        for id_aguardado in ids_aguardados_limpo:
            self.grafo_espera.add_edge(id_transacao, id_aguardado)
        return False

    def _processar_fila_espera(self):
        tamanho_a_reprocessar = len(self.fila_espera)
        if tamanho_a_reprocessar == 0:
            return

        i = 0
        while i < len(self.fila_espera):
            id_transacao, (item, modo) = self.fila_espera[i]

            if id_transacao in self.transacoes_abortadas or id_transacao in self.transacoes_commitadas:
                self.fila_espera.remove((id_transacao, (item, modo)))
                continue

            if self.grafo_espera.has_node(id_transacao):
                arestas_antigas = list(self.grafo_espera.out_edges(id_transacao))
                if arestas_antigas:
                    self.grafo_espera.remove_edges_from(arestas_antigas)

            sucesso = False
            if modo in ['S', 'U', 'X']:
                 if modo == 'S': sucesso = self._ler(id_transacao, item)
                 elif modo == 'U': sucesso = self._atualizar(id_transacao, item)
                 elif modo == 'X': sucesso = self._escrever(id_transacao, item)
            else:
                 sucesso = self._solicitar_bloqueio(id_transacao, item, modo)

            if sucesso:
                self.fila_espera.remove((id_transacao, (item, modo)))
                i = 0
            else:
                i += 1

        ids_com_operacao_pendente = list(self.operacoes_pendentes.keys())
        for id_t in ids_com_operacao_pendente:
            ### CORREÇÃO APLICADA AQUI ###
            # Verifica se a operação pendente ainda existe antes de tentar removê-la
            if id_t in self.operacoes_pendentes and not any(op[0] == id_t for op in self.fila_espera):
                operacao = self.operacoes_pendentes.pop(id_t)
                self.historico.append(f"T{id_t} não está mais em espera. Executando {operacao} pendente.")
                if operacao == 'c':
                    self._efetivar_commit(id_t)

    def _detectar_e_resolver_deadlock(self):
        try:
            ciclo = nx.find_cycle(self.grafo_espera)
            vitima = max([int(node) for node, _ in ciclo])
            self.historico.append(f"DEADLOCK detectado: {ciclo}. Vítima: T{vitima}")
            self._abortar(vitima, "deadlock")
            return True
        except nx.NetworkXNoCycle:
            return False

    def _interpretar_escalonamento(self, escalonamento_str):
        padrao = r'([rwuc])(\d+)(?:\(([\w\.]+)\))?'
        operacoes = []
        for op, id_transacao, item in re.findall(padrao, escalonamento_str):
            operacoes.append((op, int(id_transacao), item if item else None))
        return operacoes

    def processar_escalonamento(self, escalonamento_str):
        operacoes = self._interpretar_escalonamento(escalonamento_str)
        transacoes_no_escalonamento = sorted(list(set(id_t for _, id_t, _ in operacoes)))
        self.grafo_espera.add_nodes_from(transacoes_no_escalonamento)

        for op, id_transacao, item in operacoes:
            if id_transacao in self.transacoes_abortadas or id_transacao in self.transacoes_commitadas:
                continue

            if any(o[0] == id_transacao for o in self.fila_espera) and op != 'c':
                 self.historico.append(f"Operação {op}{id_transacao}({item}) ignorada pois T{id_transacao} está em espera.")
                 continue

            if op == 'r': self._ler(id_transacao, item)
            elif op == 'w': self._escrever(id_transacao, item)
            elif op == 'c': self._efetivar_commit(id_transacao)

            if self._detectar_e_resolver_deadlock():
                self._processar_fila_espera()

        for id_transacao in transacoes_no_escalonamento:
            if id_transacao not in self.transacoes_commitadas and id_transacao not in self.transacoes_abortadas:
                self._abortar(id_transacao, "não commitada")

        self._formatar_resultado()

    def _formatar_resultado(self):
        print("\n--- Histórico de Execução Detalhado ---")
        for i, op in enumerate(self.historico, 1):
            print(f"{i:02d}. {op}")
        print("\n--- Escalonamento Final Equivalente (Apenas Operações de Sucesso) ---")
        sucesso = [op for op in self.historico if re.match(r'^[rwuc]\d+(\([\w\.]+\))?$', op) or
                   re.match(r'^upgrade\d+', op)]
        print(' '.join(sucesso))

if __name__ == "__main__":
    testes = [
        #("1. Conflito Leitura-Escrita (Tupla)", "r1(TB1.P1.TU1) w2(TB1.P1.TU1) c1 c2"),
        #("2. Conflito Escrita-Escrita (Tupla)", "w1(TB1.P1.TU1) w2(TB1.P1.TU1) c1 c2"),
        #("3. Leituras Paralelas (Tupla)", "r1(TB1.P1.TU1) r2(TB1.P1.TU1) c1 c2"),
        #("4. Conflito Tabela vs. Tupla (S vs IX)", "r1(TB1) w2(TB1.P1.TU1) c1 c2"),
        #("5. Conflito Página vs. Tupla (X vs S)", "w1(TB1.P1) r2(TB1.P1.TU1) c1 c2"),
        #("6. Operações Paralelas (Tabelas Diferentes)", "r1(TB1.P1) w2(TB2.P1) c1 c2"),
        #("7. Bloqueio Total (DB)", "w1(DB) r2(TB1.P1.TU1) c1 c2"),
        #("8. Upgrade S -> X (Tupla)", "r1(TB1.P1.TU1) w1(TB1.P1.TU1) c1"),
        #("9. Upgrade U -> X (Promoção de Update)", "u1(TB1.P1.TU1) w1(TB1.P1.TU1) c1"),
        #("10. Upgrade de Intenção IS -> IX", "r1(TB1.P1.TU1) w1(TB1.P1.TU2) c1"),
        #("11. Falha de Upgrade (Conflito com S)", "r1(TB1.P1.TU1) r2(TB1.P1.TU1) w1(TB1.P1.TU1) c1 c2"),
        #("12. Deadlock Clássico (Tuplas)", "r1(TB1.P1.TU1) r2(TB1.P1.TU2) w1(TB1.P1.TU2) w2(TB1.P1.TU1) c1 c2"),
        #("13. Deadlock de Conversão (Upgrade)", "r1(TB1.P1.TU1) r2(TB1.P1.TU1) w1(TB1.P1.TU1) w2(TB1.P1.TU1) c1 c2"),
        #("14. Deadlock Hierárquico", "w1(TB1) r2(TB2.P1) w2(TB1.P1) r1(TB2.P1.TU1) c1 c2"),
        #("15. Deadlock de 3 Vias", "w1(TB1.P1.TU1) w2(TB1.P1.TU2) w3(TB2.P1.TU1) r1(TB1.P1.TU2) r2(TB2.P1.TU1) r3(TB1.P1.TU1) c1 c2 c3"),
        #("16. Abort Libera Fila de Espera", "w1(TB1.P1.TU1) w2(TB1.P1.TU1) w3(TB1.P1.TU1) c2 c3"),
        #("17. Múltiplos Esperando (FIFO)", "w1(TB1.P1.TU1) r2(TB1.P1.TU1) w3(TB1.P1.TU1) c1 c2 c3"),
        #("18. Conflito U vs U", "u1(TB1.P1.TU1) u2(TB1.P1.TU1) c1 c2"),
        #("19. Operações Após Commit (Deve ser ignorada)", "r1(TB1.P1.TU1) c1 w1(TB1.P1.TU1)"),
        #("20. Múltiplas Transações e Granularidades", "r1(TB1) w2(TB2) r3(TB1.P1.TU1) w1(TB2.P1.TU1) c1 c2 c3"),
        ("Deadlock com Commit Atrasado", "r1(TB1.P1) r2(TB1.P1.TU1) w2(TB1.P1.TU1) c2 w1(TB1.P1) c1")
    ]

    for nome, escalonamento_str in testes:
        print("\n" + "="*20 + f" {nome} " + "="*20)
        print(f"Escalonamento de Entrada: {escalonamento_str}")
        escalonador = Escalonador2PLMGU()
        escalonador.processar_escalonamento(escalonamento_str)