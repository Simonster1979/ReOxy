import asyncio
import websockets
import json

# Store active sessions
sessions = {}

async def handle_websocket(websocket, path):
    """Handle WebSocket connections and messages"""
    client_id = id(websocket)
    sessions[client_id] = {'websocket': websocket, 'authenticated': False}
    
    try:
        async for message in websocket:
            data = json.loads(message)
            
            if data['type'] == 'check_session':
                # Check if this client has an active session
                if sessions[client_id].get('authenticated'):
                    await websocket.send(json.dumps({
                        'authenticated': True,
                        'username': sessions[client_id].get('username')
                    }))
            
            elif data['type'] == 'login':
                # Store authentication state
                sessions[client_id].update({
                    'authenticated': True,
                    'username': data['username']
                })
                await websocket.send(json.dumps({'status': 'success'}))
            
            elif data['type'] == 'logout':
                sessions[client_id] = {'websocket': websocket, 'authenticated': False}
                await websocket.send(json.dumps({'status': 'logged_out'}))
                
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if client_id in sessions:
            del sessions[client_id]

async def main():
    async with websockets.serve(handle_websocket, "localhost", 8765):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main()) 