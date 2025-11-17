"""
Main CLI entry point for SecureVPN
"""

import asyncio
import sys
import signal
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from ..config import ConfigLoader, VPNConfig
from ..server import SecureVPNServer
from ..client import SecureVPNClient
from ..crypto import KeyManager
from ..exceptions import SecureVPNError

console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="SecureVPN")
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), 
              help="Configuration file path")
@click.pass_context
def cli(ctx, config):
    """SecureVPN - High-Performance Encrypted VPN Solution"""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config


@cli.command()
@click.option("--server", is_flag=True, help="Generate server key pair")
@click.option("--client", is_flag=True, help="Generate client key pair")
@click.option("--output-dir", "-o", type=click.Path(path_type=Path), default=Path("."),
              help="Output directory for keys")
@click.option("--name", "-n", default="keypair", help="Key pair name")
def generate_keys(server, client, output_dir, name):
    """Generate cryptographic key pairs"""
    
    if not server and not client:
        console.print("[red]Error: Specify --server or --client[/red]")
        sys.exit(1)
    
    try:
        key_manager = KeyManager()
        keypair = key_manager.generate_keypair()
        
        # Determine file names
        key_type = "server" if server else "client"
        private_key_path = output_dir / f"{name}_{key_type}_private.key"
        public_key_path = output_dir / f"{name}_{key_type}_public.key"
        
        # Save keys
        key_manager.save_keypair_to_files(keypair, private_key_path, public_key_path)
        
        # Display results
        table = Table(title=f"{key_type.title()} Key Pair Generated")
        table.add_column("File", style="cyan")
        table.add_column("Path", style="green")
        
        table.add_row("Private Key", str(private_key_path))
        table.add_row("Public Key", str(public_key_path))
        
        console.print(table)
        
        # Show public key for sharing
        panel = Panel(
            keypair.public_key_b64,
            title=f"{key_type.title()} Public Key (share this)",
            border_style="green"
        )
        console.print(panel)
        
    except Exception as e:
        console.print(f"[red]Error generating keys: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--server", is_flag=True, help="Create server configuration")
@click.option("--client", is_flag=True, help="Create client configuration")
@click.option("--server-address", help="Server address (for client config)")
@click.option("--server-public-key", help="Server public key (for client config)")
@click.option("--output", "-o", type=click.Path(path_type=Path), 
              help="Output configuration file")
def create_config(server, client, server_address, server_public_key, output):
    """Create configuration files"""
    
    if not server and not client:
        console.print("[red]Error: Specify --server or --client[/red]")
        sys.exit(1)
    
    try:
        if server:
            config_data = ConfigLoader.create_server_template()
            default_output = Path("server.conf")
        else:
            if not server_address or not server_public_key:
                console.print("[red]Error: Client config requires --server-address and --server-public-key[/red]")
                sys.exit(1)
            
            config_data = ConfigLoader.create_client_template(server_address, server_public_key)
            default_output = Path("client.conf")
        
        output_path = output or default_output
        
        # Create config object and save
        config = ConfigLoader.from_dict(config_data)
        ConfigLoader.to_file(config, output_path)
        
        console.print(f"[green]Configuration created: {output_path}[/green]")
        
        # Show configuration summary
        mode = "Server" if server else "Client"
        table = Table(title=f"{mode} Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        if server:
            table.add_row("Mode", "Server")
            table.add_row("Bind Address", config_data["server"]["bind_address"])
            table.add_row("Port", str(config_data["server"]["port"]))
            table.add_row("Network", config_data["network"]["ipv4_network"])
        else:
            table.add_row("Mode", "Client")
            table.add_row("Server Address", config_data["client"]["server_address"])
            table.add_row("Server Port", str(config_data["client"]["server_port"]))
        
        table.add_row("Encryption", config_data["crypto"]["cipher"])
        table.add_row("Obfuscation", config_data["obfuscation"]["method"])
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error creating configuration: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path),
              help="Server configuration file")
@click.option("--daemon", "-d", is_flag=True, help="Run as daemon")
@click.pass_context
def server(ctx, config, daemon):
    """Start VPN server"""
    
    config_path = config or ctx.obj.get('config_path')
    if not config_path:
        console.print("[red]Error: Configuration file required[/red]")
        sys.exit(1)
    
    try:
        # Load configuration
        vpn_config = ConfigLoader.from_file(config_path)
        
        if vpn_config.mode != "server":
            console.print("[red]Error: Configuration is not for server mode[/red]")
            sys.exit(1)
        
        # Show startup info
        console.print(Panel(
            f"Starting SecureVPN Server\n"
            f"Address: {vpn_config.server.bind_address}:{vpn_config.server.port}\n"
            f"Network: {vpn_config.network.ipv4_network}\n"
            f"Encryption: {vpn_config.crypto.cipher}\n"
            f"Obfuscation: {vpn_config.obfuscation.method if vpn_config.obfuscation.enabled else 'Disabled'}",
            title="SecureVPN Server",
            border_style="green"
        ))
        
        # Start server
        asyncio.run(_run_server(vpn_config, daemon))
        
    except Exception as e:
        console.print(f"[red]Error starting server: {e}[/red]")
        sys.exit(1)


async def _run_server(config: VPNConfig, daemon: bool):
    """Run the VPN server"""
    server = SecureVPNServer(config)
    
    # Setup signal handlers
    def signal_handler():
        console.print("\n[yellow]Shutting down server...[/yellow]")
        asyncio.create_task(server.stop())
    
    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
    
    try:
        await server.start()
        
        if not daemon:
            console.print("[green]Server started successfully![/green]")
            console.print("Press Ctrl+C to stop the server")
        
        # Keep running until stopped
        while server.running:
            await asyncio.sleep(1)
            
            if not daemon:
                # Show periodic stats
                stats = server.get_stats()
                if stats["active_connections"] > 0:
                    console.print(f"Active connections: {stats['active_connections']}")
    
    except KeyboardInterrupt:
        pass
    except Exception as e:
        console.print(f"[red]Server error: {e}[/red]")
    finally:
        await server.stop()


async def _run_client(config: VPNConfig, auto_reconnect: bool):
    """Run the VPN client"""
    client = SecureVPNClient(config)
    
    # Setup signal handlers
    def signal_handler():
        console.print("\n[yellow]Disconnecting from VPN...[/yellow]")
        asyncio.create_task(client.disconnect())
    
    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
    
    try:
        await client.connect()
        
        console.print("[green]VPN connection established![/green]")
        console.print("Press Ctrl+C to disconnect")
        
        # Keep running and show periodic stats
        while client.connected:
            await asyncio.sleep(5)
            
            stats = client.get_stats()
            if stats["authenticated"]:
                console.print(f"Connected: {stats['uptime']:.0f}s | "
                            f"Sent: {stats['bytes_sent']} bytes | "
                            f"Received: {stats['bytes_received']} bytes")
    
    except KeyboardInterrupt:
        pass
    except Exception as e:
        console.print(f"[red]Client error: {e}[/red]")
        
        if auto_reconnect:
            try:
                console.print("[yellow]Attempting to reconnect...[/yellow]")
                await client.auto_reconnect()
            except Exception as reconnect_error:
                console.print(f"[red]Reconnection failed: {reconnect_error}[/red]")
    finally:
        await client.disconnect()


@cli.command()
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path),
              help="Client configuration file")
@click.option("--auto-reconnect", is_flag=True, help="Enable automatic reconnection")
@click.pass_context
def client(ctx, config, auto_reconnect):
    """Start VPN client"""
    
    config_path = config or ctx.obj.get('config_path')
    if not config_path:
        console.print("[red]Error: Configuration file required[/red]")
        sys.exit(1)
    
    try:
        # Load configuration
        vpn_config = ConfigLoader.from_file(config_path)
        
        if vpn_config.mode != "client":
            console.print("[red]Error: Configuration is not for client mode[/red]")
            sys.exit(1)
        
        # Show startup info
        console.print(Panel(
            f"Starting SecureVPN Client\n"
            f"Server: {vpn_config.client.server_address}:{vpn_config.client.server_port}\n"
            f"Encryption: {vpn_config.crypto.cipher}\n"
            f"Obfuscation: {vpn_config.obfuscation.method if vpn_config.obfuscation.enabled else 'Disabled'}\n"
            f"Auto-reconnect: {'Enabled' if auto_reconnect else 'Disabled'}",
            title="SecureVPN Client",
            border_style="blue"
        ))
        
        # Start client
        asyncio.run(_run_client(vpn_config, auto_reconnect))
        
    except Exception as e:
        console.print(f"[red]Error starting client: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("config_file", type=click.Path(exists=True, path_type=Path))
def validate(config_file):
    """Validate configuration file"""
    
    try:
        config = ConfigLoader.from_file(config_file)
        
        console.print("[green]✓ Configuration is valid[/green]")
        
        # Show configuration summary
        table = Table(title="Configuration Summary")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Mode", config.mode)
        table.add_row("Encryption", config.crypto.cipher)
        table.add_row("Network", str(config.network.ipv4_network))
        table.add_row("MTU", str(config.network.mtu))
        table.add_row("Obfuscation", config.obfuscation.method if config.obfuscation.enabled else "Disabled")
        
        if config.mode == "server":
            table.add_row("Bind Address", config.server.bind_address)
            table.add_row("Port", str(config.server.port))
            table.add_row("Max Clients", str(config.server.max_clients))
        else:
            table.add_row("Server Address", config.client.server_address)
            table.add_row("Server Port", str(config.client.server_port))
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]✗ Configuration is invalid: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("public_key_file", type=click.Path(exists=True, path_type=Path))
def show_key(public_key_file):
    """Display public key information"""
    
    try:
        with open(public_key_file, 'r') as f:
            public_key_b64 = f.read().strip()
        
        # Validate key
        from ..crypto.keys import KeyPair
        keypair = KeyPair.from_public_key_b64(public_key_b64)
        
        panel = Panel(
            public_key_b64,
            title="Public Key",
            border_style="green"
        )
        console.print(panel)
        
        console.print(f"[green]✓ Valid Curve25519 public key[/green]")
        
    except Exception as e:
        console.print(f"[red]Error reading public key: {e}[/red]")
        sys.exit(1)


def main():
    """Main entry point"""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
