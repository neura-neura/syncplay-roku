sub init()
    m.captionImage = m.top.findNode("captionImage")
    m.captionPreload = m.top.findNode("captionPreload")
    m.captionImage.observeField("loadStatus", "drawCaptions")
    m.captions = m.top.findNode("captions")
    m.captionText = m.top.findNode("captionText")
    m.captionMeasure = CreateObject("roSGNode", "Label")
    m.captionMeasure.font = m.captionText.font
    m.captionCues = []
    m.captionTimer = m.top.findNode("captionTimer")
    m.captionTimer.observeField("fire", "drawCaptions")
    m.captionTimer.control = "start"
    m.remoteInput = m.top.findNode("remoteInput")
    m.remoteInput.observeField("keyEvent", "remoteKey")
    m.transport = m.top.findNode("transport")
    m.transportTimer = m.top.findNode("transportTimer")
    m.transportTimer.observeField("fire", "hideTransport")
    m.seekPending = false
    m.seekPosition = 0.0
    m.menu = m.top.findNode("menu")
    m.status = m.top.findNode("status")
    m.details = m.top.findNode("details")
    m.heading = m.top.findNode("heading")
    m.video = m.top.findNode("video")
    m.video.seekMode = "accurate"
    m.shell = m.top.findNode("shell")
    m.overlay = m.top.findNode("overlay")
    m.overlayTimer = m.top.findNode("overlayTimer")
    m.menu.observeField("itemSelected", "selected")
    m.video.observeField("state", "videoState")
    m.overlayTimer.observeField("fire", "hideOverlay")
    m.tick = m.top.findNode("tick")
    m.tick.observeField("fire", "tick")
    m.tick.control = "start"
    m.clock = CreateObject("roTimespan")
    m.clock.Mark()
    m.registry = CreateObject("roRegistrySection", "NoirSyncplay")
    defaults = ParseJson(ReadAsciiFile("pkg:/config.json"))
    if defaults = invalid then defaults = {url: "", token: ""}
    m.url = defaults.url
    m.token = defaults.token
    if m.registry.Exists("url") then m.url = m.registry.Read("url")
    if m.registry.Exists("token") then m.token = m.registry.Read("token")
    ' A paired deployment may migrate a known previous endpoint without
    ' overriding URLs the user configured for another server.
    if defaults.migrateFrom <> invalid
        if m.url = defaults.migrateFrom
            m.url = defaults.url
            m.registry.Write("url", m.url)
            m.registry.Flush()
        end if
    end if
    m.config = invalid
    m.snapshot = invalid
    m.selectedVideo = invalid
    m.selectedSubtitle = invalid
    m.currentId = ""
    m.playing = false
    m.desiredPaused = true
    m.grace = 0
    m.seekRevision = -1
    m.path = "/"
    m.sourceIndex = 0
    m.browserKind = "video"
    m.screenName = "home"
    m.task = invalid
    home()
    connect()
end sub

sub connect()
    if m.task <> invalid then m.task.control = "stop"
    m.task = CreateObject("roSGNode", "BridgeTask")
    m.task.baseUrl = m.url
    m.task.token = m.token
    m.task.observeField("configuration", "configurationChanged")
    m.task.observeField("snapshot", "snapshotChanged")
    m.task.observeField("captions", "captionsChanged")
    m.task.observeField("response", "responseChanged")
    m.task.observeField("problem", "problemChanged")
    m.config = invalid
    if m.url = "" or m.token = ""
        m.status.text = "Configura URL y clave del puente en Configuración"
        return
    end if
    m.task.control = "run"
end sub

sub api(id as String, path as String, method = "GET" as String, body = invalid as Dynamic)
    m.task.command = {id: id, path: path, method: method, body: body}
end sub

sub rows(title as String, names as Object)
    m.heading.text = title
    root = CreateObject("roSGNode", "ContentNode")
    for each name in names
        item = root.CreateChild("ContentNode")
        item.title = name
    end for
    m.menu.content = root
    m.menu.jumpToItem = 0
    m.menu.SetFocus(true)
end sub

sub home()
    m.waitingForSources = false
    m.screenName = "home"
    rows("Tu sala", ["Elegir video", "Elegir subtítulos", "Abrir / reproducir selección", "Sin subtítulos externos", "Estoy listo / No listo", "Participantes y chat", "Lista compartida", "Configuración", "Volver al video"])
    selectionDetails()
end sub

sub selectionDetails()
    text = "BIBLIOTECA REMOTA" + Chr(10) + Chr(10)
    if m.selectedVideo <> invalid then text += "Video: " + m.selectedVideo.path + Chr(10) + Chr(10)
    if m.selectedSubtitle <> invalid then text += "Subtítulos: " + m.selectedSubtitle.path + Chr(10) + Chr(10)
    text += "Configuración desde tu computadora:" + Chr(10) + m.url + Chr(10) + Chr(10) + "El puente debe permanecer encendido."
    m.details.text = text
end sub

sub selected()
    i = m.menu.itemSelected
    if m.screenName = "home"
        if i = 0 or i = 1
            m.browserKind = "video"
            if i = 1 then m.browserKind = "subtitle"
            sources()
        else if i = 2
            if m.selectedVideo = invalid
                notify("Primero selecciona un video")
            else
                api("open", "/api/open", "POST", {video: m.selectedVideo, subtitle: m.selectedSubtitle})
            end if
        else if i = 3
            m.selectedSubtitle = invalid
            selectionDetails()
        else if i = 4
            ready = true
            if m.snapshot <> invalid then ready = m.snapshot.sync.ready <> true
            api("ready", "/api/command", "POST", {kind: "ready", ready: ready})
        else if i = 5
            roomScreen()
        else if i = 6
            playlistScreen()
        else if i = 7
            settings()
        else if i = 8
            if m.currentId <> "" then showVideo()
        end if
    else if m.screenName = "sources"
        m.sourceIndex = i
        m.path = "/"
        browse()
    else if m.screenName = "browse"
        if i = 0
            parentFolder()
        else
            entry = m.entries[i - 1]
            if entry.directory
                m.path = entry.path
                browse()
            else
                choice = {source: m.sourceIndex, path: entry.path}
                if m.browserKind = "video" then m.selectedVideo = choice else m.selectedSubtitle = choice
                home()
            end if
        end if
    else if m.screenName = "settings"
        if i = 0
            keyboard("URL del puente", m.url, "bridgeUrl")
        else if i = 1
            keyboard("Clave fija del puente", m.token, "bridgeToken", true)
        else if i = 2
            if m.config <> invalid then keyboard("Servidor Syncplay", m.config.server.host, "host")
        else if i = 3
            if m.config <> invalid then keyboard("Puerto Syncplay", m.config.server.port.ToStr(), "port")
        else if i = 4
            if m.config <> invalid then keyboard("Usuario", m.config.server.username, "username")
        else if i = 5
            keyboard("Contraseña Syncplay", "", "password", true)
        else if i = 6
            keyboard("Sala", "", "room")
        else if i = 7
            sourceSettings()
        else if i = 8
            modes()
        else if i = 9
            api("pair", "/api/pair/create", "POST", {})
        end if
    else if m.screenName = "sourceSettings"
        if i = 0
            keyboard("Host SMB / FTP", m.config.sources[m.sourceIndex].host, "source.host")
        else if i = 1
            keyboard("Puerto", m.config.sources[m.sourceIndex].port.ToStr(), "source.port")
        else if i = 2
            keyboard("Protocolo: smb, ftp o ftps", m.config.sources[m.sourceIndex].protocol, "source.protocol")
        else if i = 3
            keyboard("Recurso SMB", m.config.sources[m.sourceIndex].share, "source.share")
        else if i = 4
            keyboard("Usuario", m.config.sources[m.sourceIndex].username, "source.username")
        else if i = 5
            keyboard("Contraseña", "", "source.password", true)
        else if i = 6
            keyboard("Carpeta raíz", m.config.sources[m.sourceIndex].root, "source.root")
        else if i = 7
            m.sourceIndex = (m.sourceIndex + 1) mod m.config.sources.Count()
            sourceSettings()
        else if i = 8
            m.config.sources.Push({name: "Nuevo origen", protocol: "smb", host: "", port: 445, share: "", username: "", password: "", root: "/"})
            m.sourceIndex = m.config.sources.Count() - 1
            sourceSettings()
        end if
    else if m.screenName = "modes"
        if i = 0 then m.config.video_mode = "auto"
        if i = 1 then m.config.video_mode = "direct"
        if i = 2 then m.config.video_mode = "transcode"
        if i = 3 then m.config.subtitle_mode = "text"
        if i = 4 then m.config.subtitle_mode = "burn"
        if i = 5
            keyboard("Pista de audio (desde 0)", m.config.audio_track.ToStr(), "audio_track")
        else if i = 6
            keyboard("Desfase de subtítulos en segundos", m.config.subtitle_offset.ToStr(), "subtitle_offset")
        else
            if i = 7 then m.config.autoplay = m.config.autoplay <> true
            api("saveConfig", "/api/config", "PUT", m.config)
        end if
    else if m.screenName = "room"
        if i = 0 then keyboard("Mensaje a la sala", "", "chat")
        if i = 1 then keyboard("Cambiar sala", "", "room")
        if i = 2 then keyboard("Contraseña de controlador", "", "controller", true)
    else if m.screenName = "playlist"
        if i > 0
            api("playlistIndex", "/api/command", "POST", {kind: "playlistIndex", index: i-1})
            notify("Buscando el episodio en la carpeta del video seleccionado")
        else if m.selectedVideo <> invalid and m.snapshot <> invalid
            files = m.snapshot.sync.playlist
            split = m.selectedVideo.path.Tokenize("/")
            files.Push(split[split.Count()-1])
            api("playlist", "/api/command", "POST", {kind: "playlist", files: files})
        end if
    end if
end sub

sub sources()
    if m.config = invalid
        m.waitingForSources = true
        notify("Cargando la biblioteca del puente… Se abrirá al conectar.")
        return
    end if
    m.waitingForSources = false
    m.screenName = "sources"
    names = []
    for each s in m.config.sources
        names.Push(s.name + " · " + s.protocol)
    end for
    rows("Selecciona un origen", names)
end sub

sub browse()
    m.screenName = "browse"
    m.status.text = "Leyendo " + m.path
    encoder = CreateObject("roString")
    encoder.SetString(m.path)
    api("browse", "/api/browse?source_id=" + m.sourceIndex.ToStr() + "&path=" + encoder.EncodeUriComponent())
end sub

sub parentFolder()
    if m.path = "/"
        sources()
        return
    end if
    split = m.path.Tokenize("/")
    split.Pop()
    m.path = "/" + split.Join("/")
    browse()
end sub

sub settings()
    m.screenName = "settings"
    rows("Configuración", ["URL del puente", "Clave fija del puente", "Servidor Syncplay", "Puerto Syncplay", "Usuario", "Contraseña Syncplay", "Sala", "Conexiones SMB / FTP", "Video y subtítulos", "Vincular navegador"])
    m.details.text = "Los ajustes se guardan automáticamente." + Chr(10) + Chr(10) + "Puente: " + m.url + Chr(10) + Chr(10) + "También puedes configurar desde el navegador."
end sub

sub sourceSettings()
    if m.config = invalid then return
    if m.config.sources.Count() = 0 then m.config.sources.Push({name: "Nuevo origen", protocol: "smb", host: "", port: 445, share: "", username: "", password: "", root: "/"})
    m.screenName = "sourceSettings"
    rows("Origen: " + m.config.sources[m.sourceIndex].name, ["Host / IP", "Puerto", "Protocolo", "Recurso SMB", "Usuario", "Contraseña", "Carpeta raíz", "Siguiente origen", "Agregar origen"])
end sub

sub modes()
    if m.config = invalid then return
    m.screenName = "modes"
    rows("Compatibilidad", ["Video: automático", "Video: directo", "Video: transcodificar", "Subtítulos: texto Unicode", "Subtítulos: conservar estilos ASS", "Pista de audio", "Desfase de subtítulos", "Activar / desactivar cuenta regresiva"])
    m.details.text = "Actual: " + m.config.video_mode + " / " + m.config.subtitle_mode + Chr(10) + Chr(10) + "La transcodificación prepara una copia compatible antes de reproducir. Conserva el archivo original."
end sub

sub roomScreen()
    m.screenName = "room"
    rows("Sala y chat", ["Enviar mensaje", "Cambiar sala", "Autenticar controlador"])
    roomDetails()
end sub

sub roomDetails()
    if m.snapshot = invalid then return
    text = "PARTICIPANTES" + Chr(10)
    for each room in m.snapshot.sync.users
        for each user in m.snapshot.sync.users[room]
            text += room + " · " + user + Chr(10)
        end for
    end for
    text += Chr(10) + "CHAT" + Chr(10)
    messages = m.snapshot.sync.chat
    start = messages.Count() - 7
    if start < 0 then start = 0
    for i = start to messages.Count()-1
        text += messages[i].username + ": " + messages[i].message + Chr(10)
    end for
    m.details.text = text
end sub

sub playlistScreen()
    m.screenName = "playlist"
    names = ["Agregar selección a la lista"]
    if m.snapshot <> invalid
        for each name in m.snapshot.sync.playlist
            names.Push(name)
        end for
    end if
    rows("Lista compartida", names)
end sub

sub keyboard(title as String, value as String, purpose as String, secret = false as Boolean)
    m.purpose = purpose
    dialog = CreateObject("roSGNode", "KeyboardDialog")
    dialog.title = title
    dialog.text = value
    dialog.buttons = ["Guardar", "Cancelar"]
    dialog.keyboard.textEditBox.secureMode = secret
    dialog.observeField("buttonSelected", "keyboardDone")
    m.top.dialog = dialog
end sub

sub keyboardDone()
    dialog = m.top.dialog
    if dialog.buttonSelected = 0
        value = dialog.text.Trim()
        purpose = m.purpose
        if purpose = "bridgeUrl" or purpose = "bridgeToken"
            if purpose = "bridgeUrl"
                m.url = value
                m.registry.Write("url", value)
            else
                m.token = value
                m.registry.Write("token", value)
            end if
            m.registry.Flush()
            connect()
        else if purpose = "chat" or purpose = "room" or purpose = "controller"
            api(purpose, "/api/command", "POST", {kind: purpose, text: value})
        else if m.config <> invalid
            if purpose = "audio_track" or purpose = "subtitle_offset"
                m.config[purpose] = Val(value)
            else if Left(purpose, 7) = "source."
                field = Mid(purpose, 8)
                if field = "port" then m.config.sources[m.sourceIndex][field] = Val(value) else m.config.sources[m.sourceIndex][field] = value
            else
                if purpose = "port" then m.config.server[purpose] = Val(value) else m.config.server[purpose] = value
            end if
            api("saveConfig", "/api/config", "PUT", m.config)
        end if
    end if
    dialog.close = true
    m.menu.SetFocus(true)
end sub

sub responseChanged()
    r = m.task.response
    if r.code < 200 or r.code >= 300
        text = "Error: " + r.code.ToStr()
        if r.data.detail <> invalid and type(r.data.detail) = "roString" then text = r.data.detail
        notify(text)
        return
    end if
    if r.id = "config"
        m.config = r.data
        m.selectedVideo = m.config.last_video
        m.selectedSubtitle = m.config.last_subtitle
        if m.screenName = "home" then selectionDetails()
    else if r.id = "pair"
        m.details.text = "Abre en tu teléfono o computadora:" + Chr(10) + m.url + Chr(10) + Chr(10) + "Código: " + r.data.code + Chr(10) + Chr(10) + "Válido 5 minutos, una sola vez." + Chr(10) + "Escribe este código en Vincular navegador. El panel cargará los datos guardados."
    else if r.id = "browse"
        m.entries = []
        names = [".. Volver"]
        for each e in r.data.entries
            if e.directory or e.kind = m.browserKind
                m.entries.Push(e)
                prefix = ""
                if e.directory then prefix = "+ "
                names.Push(prefix + e.name)
            end if
        end for
        rows(m.path, names)
    else if r.id = "open"
        notify("Preparando video…")
    else if r.id = "saveConfig"
        notify("Configuración guardada")
        if m.screenName = "modes" then modes()
    end if
end sub

sub problemChanged()
    if m.task.problem <> "" then m.status.text = m.task.problem
end sub

sub snapshotChanged()
    m.snapshot = m.task.snapshot
    if m.snapshot.subtitleStyle <> invalid
        style = m.snapshot.subtitleStyle
        signature = FormatJson(style)
        if m.captionStyleSignature <> signature
            m.captionStyleSignature = signature
            font = CreateObject("roSGNode", "Font")
            font.uri = "pkg:/fonts/NotoSansCJKsc-Regular.otf"
            if style.bold then font.uri = "pkg:/fonts/NotoSansCJKsc-Bold.otf"
            font.size = style.size
            m.captionText.font = font
            m.captionMeasure.font = font
            m.captionText.color = style.color
            m.top.findNode("captionBackground").opacity = style.opacity / 100.0
            m.captionText.text = ""
            if m.config <> invalid then m.config.subtitle_style = style
        end if
    end if
    s = m.snapshot.sync
    status = "Conectando a Syncplay"
    if s.connected then status = s.username + "  /  " + s.room
    if s.error <> "" then status = s.error
    media = m.snapshot.media
    if media.status = "preparing" then status += "  ·  " + media.progress
    if media.status = "error" then status += "  ·  " + media.error
    if s.ready = true then status += "  ·  Listo"
    if s.countdown <> invalid then status += "  ·  Comienza en " + s.countdown.ToStr()
    m.status.text = status
    if m.screenName = "room" then roomDetails()
    if media.current <> invalid
        if media.current.id <> m.currentId then loadVideo(media.current)
    end if
    if m.playing and s.connected and not m.seekPending and m.clock.TotalMilliseconds() > m.grace
        target = s.target
        m.desiredPaused = target.paused
        if m.video.state = "playing" or m.video.state = "paused"
            if target.paused and m.video.state = "playing" then m.video.control = "pause"
            if not target.paused and m.video.state = "paused" then m.video.control = "resume"
            difference = Abs(m.video.position - target.position)
            if (s.seekRevision <> m.seekRevision and difference > 1) or difference > 4
                m.video.seek = target.position
                m.grace = m.clock.TotalMilliseconds() + 3000
            end if
            m.seekRevision = s.seekRevision
        end if
    end if
end sub

sub loadVideo(item as Object)
    m.seekPending = false
    m.currentId = item.id
    m.captionCues = []
    m.captions.visible = false
    m.video.control = "stop"
    content = CreateObject("roSGNode", "ContentNode")
    content.url = item.url
    content.title = item.title
    content.streamFormat = item.format
    content.length = Int(item.duration)
    ' Text captions are drawn with the bundled Unicode font, independent of OS captions.
    m.video.globalCaptionMode = "Off"
    m.video.content = content
    m.video.subtitleTrack = ""
    if m.snapshot <> invalid then m.desiredPaused = m.snapshot.sync.target.paused
    m.video.notificationInterval = 0.1
    m.video.control = "play"
    m.grace = m.clock.TotalMilliseconds() + 1500
    m.seekRevision = -1
    showVideo()
end sub

sub showVideo()
    m.video.visible = true
    m.shell.visible = false
    m.playing = true
    m.remoteInput.SetFocus(true)
    showTransport()
end sub

sub videoState()
    if m.video.state = "playing" and m.desiredPaused
        m.video.control = "pause"
    else if m.video.state = "error"
        notify("No se pudo reproducir: " + m.video.errorMsg + ". Prueba video automático o transcodificación.")
        m.playing = false
        hideTransport()
        m.video.visible = false
        m.shell.visible = true
        home()
    else if m.video.state = "finished"
        if m.snapshot <> invalid and m.config <> invalid
            idx = m.snapshot.sync.playlistIndex
            if m.config.follow_playlist and idx <> invalid
                if idx + 1 < m.snapshot.sync.playlist.Count()
                    api("playlistIndex", "/api/command", "POST", {kind: "playlistIndex", index: idx + 1})
                end if
            end if
        end if
        m.playing = false
        hideTransport()
        m.video.visible = false
        m.shell.visible = true
        home()
    end if
end sub

sub tick()
    if m.seekPending and m.clock.TotalMilliseconds() > m.seekDeadline
        m.seekPending = false
        localAction(m.seekPosition, m.desiredPaused, true)
    end if
    if m.transport.visible then updateTransport()
    if m.task = invalid then return
    m.task.telemetry = {position: m.video.position, paused: m.video.state <> "playing", active: m.playing and (m.video.state = "playing" or m.video.state = "paused")}
end sub

sub notify(text as String)
    m.overlay.text = text
    m.overlay.visible = true
    m.overlayTimer.control = "start"
end sub

sub hideOverlay()
    m.overlay.visible = false
end sub

sub localAction(position as Float, paused as Boolean, seek = false as Boolean)
    if m.snapshot = invalid then return
    if not m.snapshot.sync.connected
        notify("Sin conexión a Syncplay")
        return
    end if
    m.desiredPaused = paused
    if paused then m.video.control = "pause" else m.video.control = "resume"
    if seek then m.video.seek = position
    m.grace = m.clock.TotalMilliseconds() + 4000
    api("action", "/api/action", "POST", {position: position, paused: paused, seek: seek})
end sub

function timeText(seconds as Float) as String
    total = Int(seconds)
    if total < 0 then total = 0
    minutes = Int(total / 60)
    secs = total mod 60
    prefix = ""
    if minutes >= 60
        prefix = Int(minutes / 60).ToStr() + ":"
        minutes = minutes mod 60
    end if
    return prefix + Right("0" + minutes.ToStr(), 2) + ":" + Right("0" + secs.ToStr(), 2)
end function

sub updateTransport()
    if m.video.content = invalid then return
    m.top.findNode("transportTitle").text = m.video.content.title
    position = m.video.position
    if m.seekPending then position = m.seekPosition
    duration = m.video.content.length
    text = "Reproduciendo"
    if m.desiredPaused then text = "Pausado"
    if m.video.state = "buffering" then text = "Cargando"
    if m.seekPending then text = "Ir a " + timeText(position)
    if m.snapshot <> invalid
        text += "  ·  " + m.snapshot.sync.room
        if not m.snapshot.sync.connected then text += "  ·  Sin conexión"
    end if
    m.top.findNode("transportState").text = text
    m.top.findNode("transportTime").text = timeText(position) + " / " + timeText(duration)
    width = 0.0
    if duration > 0 then width = 1740 * position / duration
    if width > 1740 then width = 1740
    if width < 0 then width = 0
    m.top.findNode("transportProgress").width = width
end sub

sub showTransport()
    if not m.video.visible then return
    updateTransport()
    m.transport.visible = true
    m.transportTimer.control = "stop"
    m.transportTimer.control = "start"
end sub

sub hideTransport()
    m.transport.visible = false
end sub

sub queueSeek(delta as Float)
    if not m.seekPending then m.seekPosition = m.video.position
    m.seekPosition += delta
    if m.seekPosition < 0 then m.seekPosition = 0
    if m.video.content <> invalid
        if m.video.content.length > 0 and m.seekPosition > m.video.content.length - 1
            m.seekPosition = m.video.content.length - 1
        end if
    end if
    m.seekPending = true
    m.seekDeadline = m.clock.TotalMilliseconds() + 450
    showTransport()
end sub

function onKeyEvent(key as String, press as Boolean) as Boolean
    if not press then return false
    if m.video.visible
        if key = "play" or key = "OK" or key = "pause"
            if m.seekPending
                m.seekPending = false
                localAction(m.seekPosition, m.desiredPaused, true)
            else
                paused = not m.desiredPaused
                if key = "pause" then paused = true
                localAction(m.video.position, paused)
            end if
            showTransport()
            return true
        else if key = "right"
            queueSeek(10)
            return true
        else if key = "fastforward" or key = "fwd"
            queueSeek(30)
            return true
        else if key = "left" or key = "replay"
            queueSeek(-10)
            return true
        else if key = "rewind" or key = "rev"
            queueSeek(-30)
            return true
        else if key = "up" or key = "info"
            showTransport()
            return true
        else if key = "down"
            hideTransport()
            return true
        else if key = "back" or key = "options"
            m.seekPending = false
            localAction(m.video.position, true)
            hideTransport()
            m.video.visible = false
            m.shell.visible = true
            home()
            return true
        end if
        showTransport()
    else if key = "back"
        if m.screenName = "browse"
            parentFolder()
        else if m.screenName <> "home"
            home()
        else
            return false
        end if
        return true
    end if
    return false
end function

sub transportCommand()
    command = m.top.transportCommand
    status = "error"
    if m.video.visible
        status = "success"
        if command.command = "play" or command.command = "resume"
            localAction(m.video.position, false)
        else if command.command = "pause" or command.command = "stop"
            localAction(m.video.position, true)
        else if command.command = "forward"
            queueSeek(30)
        else if command.command = "rewind"
            queueSeek(-30)
        else if command.command = "replay"
            queueSeek(-10)
        else if command.command = "startover"
            localAction(0, m.desiredPaused, true)
        else if command.command = "seek"
            delta = 10.0
            if command.duration <> invalid then delta = Val(command.duration.ToStr())
            if command.direction = "backward" then delta = -delta
            queueSeek(delta)
        else
            status = "error"
        end if
        showTransport()
    end if
    m.top.transportResponse = {id: command.id, status: status}
end sub

sub remoteKey()
    event = m.remoteInput.keyEvent
    handled = onKeyEvent(event.key, event.press)
end sub

sub captionsChanged()
    data = m.task.captions
    if data = invalid then return
    if data.id <> m.currentId then return
    m.captionCues = data.cues
    drawCaptions()
end sub

sub drawCaptions()
    m.captions.visible = false
    m.captionImage.visible = false
    if not m.playing or not m.video.visible then return
    if m.video.state <> "playing" and m.video.state <> "paused" then return
    position = m.video.position * 1000
    lo = 0
    hi = m.captionCues.Count() - 1
    found = -1
    while lo <= hi
        mid = Int((lo + hi) / 2)
        cue = m.captionCues[mid]
        if position < cue.start
            hi = mid - 1
        else if position >= cue.end
            lo = mid + 1
        else
            found = mid
            exit while
        end if
    end while
    if m.snapshot <> invalid and m.snapshot.captionRevision <> invalid
        nextIndex = lo
        if found >= 0 then nextIndex = found + 1
        if nextIndex < m.captionCues.Count()
            nextUri = captionUri(nextIndex)
            if m.captionPreload.uri <> nextUri then m.captionPreload.uri = nextUri
        end if
        if found < 0 then return
        uri = captionUri(found)
        if m.captionImage.uri <> uri then m.captionImage.uri = uri
        if m.captionImage.loadStatus = "ready"
            m.captionImage.width = m.captionImage.bitmapWidth
            m.captionImage.height = m.captionImage.bitmapHeight
            bottom = 1080 * (1 - m.snapshot.subtitleStyle.bottom / 100.0)
            if m.transport.visible and bottom > 775 then bottom = 775
            top = bottom - m.captionImage.bitmapHeight
            if top < 0 then top = 0
            m.captionImage.translation = [(1920 - m.captionImage.bitmapWidth) / 2, top]
            m.captionImage.visible = true
        end if
        return
    end if
    if found < 0 then return
    text = m.captionCues[found].text
    if m.captionText.text <> text
        ' Measure each explicit line using the same font; keep wrapping for long cues.
        width = 1.0
        for each line in text.Split(Chr(10))
            m.captionMeasure.text = line
            measured = m.captionMeasure.boundingRect().width + 2
            if measured > width then width = measured
        end for
        if width > 1700 then width = 1700
        m.captionText.width = width
        m.captionText.text = text
        m.top.findNode("captionBackground").width = width + 40
    end if
    bounds = m.captionText.boundingRect()
    height = bounds.height + 16
    if height > 520 then height = 520
    m.top.findNode("captionBackground").height = height
    bottom = 1010
    if m.transport.visible then bottom = 775
    m.captions.translation = [(1920 - m.captionText.width - 40) / 2, bottom - height]
    m.captions.visible = true
end sub

sub configurationChanged()
    m.config = m.task.configuration
    m.selectedVideo = m.config.last_video
    m.selectedSubtitle = m.config.last_subtitle
    if m.waitingForSources = true
        sources()
    else if m.screenName = "home"
        selectionDetails()
    end if
end sub

function captionUri(index as Integer) as String
    return m.url + "/api/caption/" + m.currentId + "/" + index.ToStr() + "/" + m.snapshot.captionRevision + ".png?token=" + m.token
end function
