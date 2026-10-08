"""Authored bindings for direct recorded-field retrieval, not generic usefulness.

Other counters may help derivation or diagnosis. Binary labels below apply only
to the explicitly requested *direct record*. Broader questions stay UNKNOWN;
their original blocks must be retained. Primary API meanings are independently
checked against actual raw receipts, but these language aliases are authored.
"""

REFERENCES = {
    'retry': 'https://tenacity.readthedocs.io/en/stable/api.html',
    'udp': 'https://docs.python.org/3.13/library/socket.html',
    'git': 'https://git-scm.com/docs/git-status',
}

# Each role: source, unit, four English intents, four Portuguese intents,
# and four separately authored English report captions.
ROLES = {
    'retry_attempts': ('retry', 'calls',
        ('total retry attempts including the first call', 'all operation calls made by the retry loop', 'number of attempts from initial invocation to success', 'complete count of executions in the retry sequence'),
        ('total de tentativas incluindo a primeira chamada', 'todas as chamadas da operação no laço de retry', 'número de tentativas da invocação inicial até o sucesso', 'contagem completa de execuções na sequência de retry'),
        ('Retrying attempt_number observed at success', 'Initial call plus all repeated calls', 'Total invocations logged by the retry callback', 'Operation attempt events, counting the initial execution')),
    'retry_failures': ('retry', 'calls',
        ('failed retry calls', 'attempts that raised an exception', 'unsuccessful invocations before completion', 'count of failed executions in the retry loop'),
        ('chamadas de retry que falharam', 'tentativas que geraram uma exceção', 'invocações sem sucesso antes da conclusão', 'contagem de execuções falhas no laço de retry'),
        ('Exception-bearing attempts recorded by Retrying', 'Failed operation calls before success', 'Callback events marked as unsuccessful', 'Retry attempt failures observed before termination')),
    'retry_sleep_calls': ('retry', 'calls',
        ('retry sleep callback count', 'number of waits invoked between attempts', 'calls to the retry sleeper', 'total inter-attempt sleep invocations'),
        ('contagem de chamadas ao sleep do retry', 'número de esperas invocadas entre tentativas', 'chamadas à função de espera do retry', 'total de invocações de sleep entre tentativas'),
        ('Sleep callback invocations observed by Retrying', 'Inter-attempt wait event count', 'Recorded calls to the bounded retry sleeper', 'Number of executed sleep callbacks')),
    'retry_scheduled_sleep_ns': ('retry', 'nanoseconds',
        ('planned retry sleep time', 'sum of scheduled inter-attempt delays', 'nominal waiting duration assigned by the retry policy', 'total requested sleep interval'),
        ('tempo de espera planejado no retry', 'soma dos atrasos programados entre tentativas', 'duração nominal de espera atribuída pela política de retry', 'intervalo total de sleep solicitado'),
        ('Scheduled delay sum from Retrying idle_for in nanoseconds', 'Nominal retry backoff nanoseconds', 'Total sleep duration requested by wait_fixed', 'Planned intervals passed to the sleep callback in nanoseconds')),
    'retry_actual_sleep_ns': ('retry', 'nanoseconds',
        ('actual time inside retry sleep callbacks', 'observed duration spent sleeping between attempts', 'measured sleeper execution time', 'elapsed time within the invoked retry waits'),
        ('tempo real dentro dos callbacks de sleep do retry', 'duração observada dormindo entre tentativas', 'tempo de execução medido da função de espera', 'tempo transcorrido dentro das esperas invocadas pelo retry'),
        ('Measured sleep callback nanoseconds from monotonic timestamps', 'Observed time spent inside the retry sleeper', 'Sum of actual before-and-after sleep durations in nanoseconds', 'Real callback waiting time, excluding operation calls, in nanoseconds')),
    'retry_elapsed_ns': ('retry', 'nanoseconds',
        ('whole retry operation elapsed time', 'end-to-end duration of the retry sequence', 'total real time including calls and waiting', 'wall-clock duration from retry start until success'),
        ('tempo total transcorrido da operação de retry', 'duração de ponta a ponta da sequência de retry', 'tempo real total incluindo chamadas e esperas', 'duração no relógio do início do retry até o sucesso'),
        ('Full Retrying invocation elapsed nanoseconds', 'Monotonic start-to-finish retry duration', 'Operation calls and sleeps together in nanoseconds', 'Entire retry-loop wall duration measured around Retrying')),
    'udp_sent_datagrams': ('udp', 'datagrams',
        ('UDP datagrams sent', 'number of outgoing UDP messages', 'count of sendto datagram events', 'total datagrams emitted including empty payloads'),
        ('datagramas UDP enviados', 'número de mensagens UDP de saída', 'contagem de eventos de datagrama sendto', 'total de datagramas emitidos incluindo conteúdos vazios'),
        ('Outgoing sendto event count, empty payloads included', 'Sent UDP message total', 'Number of locally transmitted UDP datagrams', 'Datagram submissions observed on the sending socket')),
    'udp_received_datagrams': ('udp', 'datagrams',
        ('UDP datagrams received', 'number of incoming UDP messages', 'count of recvfrom datagram events', 'total arrivals including empty payloads'),
        ('datagramas UDP recebidos', 'número de mensagens UDP de entrada', 'contagem de eventos de datagrama recvfrom', 'total de chegadas incluindo conteúdos vazios'),
        ('Incoming recvfrom event count, empty payloads included', 'Received UDP message total', 'Number of locally delivered UDP datagrams', 'Datagram arrivals observed on the receiving socket')),
    'udp_sent_payload_bytes': ('udp', 'bytes',
        ('UDP payload bytes sent', 'total outgoing message content length', 'sum of bytes passed as datagram payloads', 'sent application-data volume excluding network headers'),
        ('bytes de conteúdo UDP enviados', 'comprimento total do conteúdo das mensagens de saída', 'soma dos bytes passados como conteúdo de datagramas', 'volume de dados enviados sem cabeçalhos de rede'),
        ('Sum of sendto payload lengths in bytes', 'Outgoing UDP application-content byte total', 'Sent data bytes, excluding IP and UDP headers', 'Content volume submitted to the datagram socket in bytes')),
    'udp_received_payload_bytes': ('udp', 'bytes',
        ('UDP payload bytes received', 'total incoming message content length', 'sum of bytes returned as datagram payloads', 'received application-data volume excluding network headers'),
        ('bytes de conteúdo UDP recebidos', 'comprimento total do conteúdo das mensagens de entrada', 'soma dos bytes retornados como conteúdo de datagramas', 'volume de dados recebidos sem cabeçalhos de rede'),
        ('Sum of recvfrom payload lengths in bytes', 'Incoming UDP application-content byte total', 'Delivered data bytes, excluding IP and UDP headers', 'Content volume returned by the datagram socket in bytes')),
    'git_index_files': ('git', 'paths',
        ('Git index file count', 'number of tracked paths listed in the index', 'all file entries known to Git including a deleted worktree file', 'total cached file paths'),
        ('contagem de arquivos no índice do Git', 'número de caminhos rastreados listados no índice', 'todas as entradas conhecidas pelo Git incluindo um arquivo removido do diretório de trabalho', 'total de caminhos de arquivos no cache do índice'),
        ('Paths returned by git ls-files --cached -z', 'Tracked index entry total', 'Cached Git paths including missing worktree files', 'Number of indexed file names reported by Git')),
    'git_untracked_files': ('git', 'paths',
        ('untracked Git file count', 'number of files outside the index and ignore rules', 'untracked nonignored paths in the worktree', 'total unknown file entries reported by Git'),
        ('contagem de arquivos não rastreados pelo Git', 'número de arquivos fora do índice e das regras de ignore', 'caminhos não rastreados e não ignorados no diretório de trabalho', 'total de entradas de arquivo desconhecidas informado pelo Git'),
        ('Paths returned by git ls-files --others --exclude-standard', 'Nonignored untracked path total', 'Git status entries with the question-mark pair', 'Number of new files absent from the Git index')),
    'git_ignored_files': ('git', 'paths',
        ('ignored Git file count', 'number of untracked paths excluded by ignore rules', 'ignored files present in the worktree', 'total file entries matching the repository ignore patterns'),
        ('contagem de arquivos ignorados pelo Git', 'número de caminhos não rastreados excluídos pelas regras de ignore', 'arquivos ignorados presentes no diretório de trabalho', 'total de entradas que correspondem aos padrões de ignore do repositório'),
        ('Paths returned by git ls-files --others --ignored --exclude-standard', 'Ignored untracked path total', 'Git status entries with the exclamation-mark pair', 'Number of present files excluded by Git ignore patterns')),
    'git_index_edits': ('git', 'paths',
        ('paths with staged index edits', 'number of changes in the first Git status column', 'indexed paths changed against the committed tree', 'total files whose index state differs from HEAD'),
        ('caminhos com alterações preparadas no índice', 'número de alterações na primeira coluna de status do Git', 'caminhos do índice alterados em relação à árvore commitada', 'total de arquivos cujo estado no índice difere do HEAD'),
        ('Nonblank index-status columns in Git porcelain output', 'Staged path change count', 'File entries modified between HEAD and the index', 'Git status X-column edits, counting each path once')),
    'git_worktree_edits': ('git', 'paths',
        ('paths with unstaged worktree edits', 'number of changes in the second Git status column', 'tracked paths changed on disk against the index', 'total files whose worktree state differs from the index'),
        ('caminhos com alterações não preparadas no diretório de trabalho', 'número de alterações na segunda coluna de status do Git', 'caminhos rastreados alterados no disco em relação ao índice', 'total de arquivos cujo estado no diretório de trabalho difere do índice'),
        ('Nonblank worktree-status columns in Git porcelain output', 'Unstaged path change count including deletion', 'Tracked file entries modified between index and disk', 'Git status Y-column edits, counting each path once')),
    'git_clean_tracked_files': ('git', 'paths',
        ('unchanged tracked Git file count', 'number of indexed paths without index or worktree edits', 'clean file entries matching both HEAD and index', 'total tracked files absent from changed status rows'),
        ('contagem de arquivos rastreados sem alterações no Git', 'número de caminhos no índice sem alterações preparadas ou locais', 'entradas de arquivo limpas iguais ao HEAD e ao índice', 'total de arquivos rastreados ausentes das linhas alteradas de status'),
        ('Indexed paths without either Git status edit column', 'Clean tracked path total', 'File entries with no staged or unstaged changes', 'Number of unchanged files from index minus changed tracked paths')),
    'git_tracked_fs_bytes': ('git', 'bytes',
        ('current bytes of tracked files on disk', 'worktree content size of existing index paths', 'sum of file lengths for tracked paths still present', 'data volume in current tracked worktree files'),
        ('bytes atuais dos arquivos rastreados no disco', 'tamanho do conteúdo local dos caminhos existentes no índice', 'soma dos comprimentos dos arquivos rastreados ainda presentes', 'volume de dados nos arquivos rastreados atuais do diretório de trabalho'),
        ('Byte lengths of existing worktree files named in the index', 'Present tracked file content bytes', 'Tracked on-disk data total excluding the deleted path', 'Current filesystem byte volume for indexed paths that exist')),
    'git_untracked_fs_bytes': ('git', 'bytes',
        ('current bytes of nonignored untracked files', 'worktree content size outside the index excluding ignored files', 'sum of file lengths for new untracked paths', 'data volume in files Git has not yet tracked'),
        ('bytes atuais dos arquivos não rastreados e não ignorados', 'tamanho do conteúdo local fora do índice excluindo arquivos ignorados', 'soma dos comprimentos dos arquivos novos não rastreados', 'volume de dados nos arquivos que o Git ainda não rastreia'),
        ('Byte lengths of nonignored untracked worktree paths', 'New untracked file content bytes', 'Nonindexed on-disk data total after ignore filtering', 'Current filesystem byte volume for Git untracked paths')),
}

TRAIN_FAMILIES = {
    'retry_calls': ('retry_attempts', 'retry_failures'),
    'retry_count_vs_wait': ('retry_sleep_calls', 'retry_scheduled_sleep_ns'),
    'retry_sleep_vs_total': ('retry_actual_sleep_ns', 'retry_elapsed_ns'),
    'udp_sent_count_vs_bytes': ('udp_sent_datagrams', 'udp_sent_payload_bytes'),
    'udp_received_count_vs_bytes': ('udp_received_datagrams', 'udp_received_payload_bytes'),
    'git_index_vs_ignored': ('git_index_files', 'git_ignored_files'),
    'git_untracked_vs_clean': ('git_untracked_files', 'git_clean_tracked_files'),
    'git_index_vs_worktree_edits': ('git_index_edits', 'git_worktree_edits'),
    'git_tracked_vs_untracked_bytes': ('git_tracked_fs_bytes', 'git_untracked_fs_bytes'),
}

FINAL_FAMILIES = {
    'retry_attempts_vs_wait': ('retry_attempts', 'retry_scheduled_sleep_ns'),
    'retry_scheduled_vs_actual': ('retry_scheduled_sleep_ns', 'retry_actual_sleep_ns'),
    'udp_sent_vs_received_count': ('udp_sent_datagrams', 'udp_received_datagrams'),
    'udp_sent_vs_received_bytes': ('udp_sent_payload_bytes', 'udp_received_payload_bytes'),
    'git_index_vs_untracked': ('git_index_files', 'git_untracked_files'),
    'git_clean_vs_worktree_edits': ('git_clean_tracked_files', 'git_worktree_edits'),
}

TEMPLATES = {
    'train': {'en': ('Select the direct recorded value of {}.', 'Which record explicitly states {}?'),
              'pt': ('Selecione o valor registrado diretamente de {}.', 'Qual registro informa explicitamente {}?')},
    'validation': {'en': ('I need the observation that directly reports {}.',),
                   'pt': ('Preciso da observação que relata diretamente {}.',)},
    'final': {'en': ('Retrieve the explicit measurement record for {}.',),
              'pt': ('Recupere o registro explícito da medição de {}.',)},
}

UNKNOWN = {
    'train': {
        'en': ('Calculate a missing counter using the other measurements.', 'Explain the root cause of the operation failure.', 'Keep every measurement that could help fix this system.'),
        'pt': ('Calcule um contador ausente usando as outras medições.', 'Explique a causa principal da falha da operação.', 'Mantenha toda medição que possa ajudar a corrigir esse sistema.')},
    'validation': {
        'en': ('Infer the unreported value from multiple related fields.', 'What caused this operation to fail?', 'Select all evidence useful for resolving the overall incident.'),
        'pt': ('Infira o valor não informado a partir de vários campos relacionados.', 'O que causou essa operação a falhar?', 'Selecione toda evidência útil para resolver o incidente geral.')},
    'final': {
        'en': ('Derive the answer by combining the available counters.', 'Diagnose why this system operation failed.', 'Choose whichever observations could aid the broader investigation.'),
        'pt': ('Derive a resposta combinando os contadores disponíveis.', 'Diagnostique por que essa operação do sistema falhou.', 'Escolha as observações que possam ajudar na investigação mais ampla.')},
}
