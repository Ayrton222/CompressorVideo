# Compressor de Vídeo

Aplicativo desktop em Python para reduzir vídeos a um tamanho máximo aproximado. Ele usa H.264 em duas passagens, o que distribui melhor a qualidade e torna o tamanho final previsível.

## Pré-requisitos

- Python 3.10 ou superior (Tkinter já acompanha a instalação padrão do Windows)
- Conexão com a internet na primeira execução, caso o FFmpeg ainda não esteja instalado

Se o FFmpeg não estiver disponível, o próprio aplicativo oferece o download e a configuração automática,
sem solicitar permissões de administrador. Os arquivos ficam em
`%LOCALAPPDATA%\CompressorVideo\ffmpeg\bin`.

## Executar

Abra `main.py` no PyCharm e use **Run**, ou execute com o interpretador configurado no projeto.

1. Escolha o vídeo de entrada.
2. Defina o tamanho máximo desejado em MB.
3. O modo automático reduz vídeos 4K para 1080p, oferecendo boa qualidade com processamento bem mais rápido. Se precisar preservar 4K, escolha **Manter original**.
4. Clique em **Comprimir vídeo**.

O original nunca é alterado. O resultado é um MP4 compatível com celulares, navegadores e redes sociais.

## Gerar o executável do Windows

No PowerShell, dentro da pasta do projeto, execute:

```powershell
.\build.ps1
```

O aplicativo será criado em `dist\CompressorVideo.exe`. Ele funciona sem uma
instalação separada do Python. Na primeira compressão, o aplicativo oferece o
download do FFmpeg caso ele ainda não esteja disponível no computador.

## Observações

- O tamanho é aproximado; existe uma reserva de 2% para os metadados do MP4.
- **Rápida (recomendado)** é o melhor ponto de partida. Os modos de maior qualidade usam mais processamento.
- A compressão pode demorar porque o vídeo é processado duas vezes.
- Durante o processo, a tela mostra porcentagem, tempo decorrido, velocidade e estimativa restante.
