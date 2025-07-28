# 2PL-rigoroso

Trabalho final da disciplina de SGBD da Universidade Federal do Ceará

2PL-Rigoroso (Strict Two-Phase Locking com Granularidade e Upgrades)
Este projeto implementa um escalonador transacional baseado no protocolo de bloqueio em duas fases (2PL), com suporte a bloqueios com granularidade múltipla, detecção de deadlocks, modos de bloqueio sofisticados e promoção de bloqueios (upgrades).

📌 O que é o 2PL?
Two-Phase Locking (2PL) é um protocolo amplamente utilizado em sistemas de banco de dados para garantir isolamento entre transações concorrentes e manter a consistência dos dados. Ele opera em duas fases:

Fase de Expansão: a transação pode adquirir bloqueios, mas não pode liberar nenhum.

Fase de Liberação: a partir do momento em que um bloqueio é liberado, a transação não pode adquirir novos.

Este projeto implementa a variante rigorosa do 2PL, onde os bloqueios são mantidos até o commit ou abort da transação, garantindo serialização estrita.

🧠 Recursos da Implementação
Hierarquia de recursos (BD → Tabelas → Páginas → Tuplas), permitindo controle fino sobre onde o bloqueio é aplicado.

Bloqueios com múltiplos modos:

IS, IX: intenções para leitura e escrita

S: leitura compartilhada

X: escrita exclusiva

U: atualização (leitura seguida de possível escrita)

Upgrade de bloqueios, por exemplo: de S para X, IS para IX, etc.

Controle de deadlock com grafo de espera e detecção por ciclos

Fila de espera FIFO para operações bloqueadas

Histórico detalhado da execução e do escalonamento final equivalente

Resolução automática de conflitos, inclusive em cenários de deadlock ou espera circular

🧪 Exemplos de uso
O código já inclui diversos testes com diferentes tipos de conflitos:

Leitura e escrita na mesma tupla

Upgrades de bloqueio

Acesso concorrente a diferentes níveis da hierarquia

Deadlocks clássicos e complexos (até 3 vias)

Liberação de recursos após abort ou commit

Basta executar o script principal (python nome_do_arquivo.py) e os testes serão processados automaticamente com logs completos.

🛠️ Estrutura do Código
O núcleo do projeto está na classe Escalonador2PLMGU, com métodos para:

Processamento de operações de leitura, escrita e update

Solicitação e upgrade de bloqueios

Gerenciamento da fila de espera

Detecção e tratamento de deadlocks

Interpretação e execução de escalonamentos a partir de strings como r1(TB1.P1.TU1) w2(TB1.P1.TU1) c1 c2

Se quiser, posso gerar um README.md completo com markdown e inserir uma tabela ou diagrama, dependendo da sua preferência. Deseja isso também?
