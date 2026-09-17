sub init()
    m.top.functionName = "runBridge"
end sub

function request(path as String, method = "GET" as String, body = invalid as Dynamic) as Object
    transfer = CreateObject("roUrlTransfer")
    port = CreateObject("roMessagePort")
    transfer.SetMessagePort(port)
    transfer.SetUrl(m.top.baseUrl + path)
    transfer.AddHeader("X-Access-Token", m.top.token)
    transfer.AddHeader("Content-Type", "application/json")
    transfer.SetCertificatesFile("common:/certs/ca-bundle.crt")
    transfer.InitClientCertificates()
    transfer.SetRequest(method)
    if method = "GET"
        started = transfer.AsyncGetToString()
    else
        started = transfer.AsyncPostFromString(FormatJson(body))
    end if
    if started
        event = wait(15000, port)
        if type(event) = "roUrlEvent"
            data = invalid
            if event.GetString() <> "" then data = ParseJson(event.GetString())
            if data = invalid then data = {}
            return {code: event.GetResponseCode(), data: data}
        end if
    end if
    transfer.AsyncCancel()
    return {code: 0, data: {detail: "No se puede conectar al puente"}}
end function

sub runBridge()
    port = CreateObject("roMessagePort")
    m.top.observeField("command", port)
    clock = CreateObject("roTimespan")
    clock.Mark()
    captionId = ""
    configLoaded = false
    lastConfig = -2000
    lastPoll = -1000
    lastTelemetry = -1000
    while true
        msg = wait(50, port)
        if type(msg) = "roSGNodeEvent"
            command = msg.GetData()
            result = request(command.path, command.method, command.body)
            result.id = command.id
            m.top.response = result
        end if
        now = clock.TotalMilliseconds()
        ' Bootstrap here, after the task is running. Retry until a valid response arrives.
        if not configLoaded and now - lastConfig >= 2000
            configuration = request("/api/config")
            if configuration.code = 200 and configuration.data.sources <> invalid
                m.top.configuration = configuration.data
                configLoaded = true
                m.top.problem = ""
            else
                m.top.problem = "Conectando al puente; reintentando automáticamente"
                if configuration.code = 401 then m.top.problem = "La clave del puente fue rechazada. Revisa Configuración."
            end if
            lastConfig = clock.TotalMilliseconds()
        end if
        if now - lastTelemetry >= 1000
            if m.top.telemetry <> invalid
                ignored = request("/api/telemetry", "POST", m.top.telemetry)
            end if
            lastTelemetry = now
        end if
        if now - lastPoll >= 500
            result = request("/api/state")
            if result.code = 200
                m.top.snapshot = result.data
                m.top.problem = ""
                item = result.data.media.current
                if item <> invalid
                    if item.id <> captionId
                        if item.subtitleTimeline <> invalid and item.subtitleTimeline <> ""
                            captions = request(item.subtitleTimeline)
                            if captions.code = 200
                                m.top.captions = {id: item.id, cues: captions.data.cues}
                                captionId = item.id
                            else
                                m.top.problem = "No se pudieron cargar los subtítulos; reintentando"
                            end if
                        else
                            m.top.captions = {id: item.id, cues: []}
                            captionId = item.id
                        end if
                    end if
                end if
            else
                problem = "Error de conexión: " + result.code.ToStr()
                if result.data.detail <> invalid then problem = result.data.detail
                m.top.problem = problem
            end if
            lastPoll = now
        end if
    end while
end sub
