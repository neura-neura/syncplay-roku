sub Main(args as Dynamic)
    screen = CreateObject("roSGScreen")
    port = CreateObject("roMessagePort")
    screen.SetMessagePort(port)
    scene = screen.CreateScene("MainScene")
    input = CreateObject("roInput")
    input.SetMessagePort(port)
    input.EnableTransportEvents()
    scene.observeField("transportResponse", port)
    screen.Show()
    while true
        msg = wait(0, port)
        if type(msg) = "roInputEvent"
            if msg.IsInput()
                data = msg.GetInfo()
                if data.type = "transport" then scene.transportCommand = data
            end if
        else if type(msg) = "roSGNodeEvent"
            input.EventResponse(msg.GetData())
        end if
        if type(msg) = "roSGScreenEvent" and msg.IsScreenClosed() then return
    end while
end sub
