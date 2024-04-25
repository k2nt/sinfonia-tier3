import os
import time
import subprocess
import shutil
from pathlib import Path

import typer
from yarl import URL

from loadtest.config import Config


app = typer.Typer()


@app.command()
def loadtest(
        config_path: str = typer.Option('src/loadtest/.cli.toml'),
        headless: bool = typer.Option(False),
        tier2_url: str = typer.Option(""),
):    
    config = Config(config_path)
    if tier2_url:
        config.c["network"]["app_root_url"] = str(URL(tier2_url).with_port(30080) / "api" / "v1")
        config.c["network"]["tier2_root_url"] = str(URL(tier2_url).with_port(30051) / "api" / "v1")
    
    if not headless:
        print(repr(config))
    
        proceed = typer.confirm('Proceed?')
        if not proceed:
            raise typer.Abort()
    
        print('\nStarting ...\n')
    
    # Create report folder for current session
    if config.c['cli']['is_report']:
        os.makedirs(config.c['report']['report_root_path'], exist_ok=True)
    
    # Execute loadtest at different RPS
    for t, rps_per_user in enumerate(config.c['load']['rps_per_users']):
        # Cooldown
        if t != 0:
            print('Done! 45-second cool down ...')
            for i in range(45, 0, -1):
                if i % 5 == 0:
                    print(f"{i} ...", end="", flush=True)
                time.sleep(1)
            print()
        
        num_users = config.c['load']['users']
        print(f'Running loadtest @ {rps_per_user * num_users * 10} req/sec ...', flush=True)
        
        # Export locust config to file
        config.export_cli_to_toml(str(Path(config_path).parent / ".locust.autogen.toml"), rps_per_user)
        
        locust_command = shutil.which("locust")
        assert locust_command is not None
        
        loadtest_command = [locust_command] + config.to_locust_args(rps_per_user)
        
        loadtest_proc = subprocess.Popen(
            loadtest_command,
            text=True,
            )
        
        _ = loadtest_proc.wait()
        
        

if __name__ == '__main__':
    app()
