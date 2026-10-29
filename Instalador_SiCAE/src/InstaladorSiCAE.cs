using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

namespace InstaladorSiCAE
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            // Habilitar TLS 1.2 para descargas desde GitHub
            ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072 | SecurityProtocolType.Tls11 | SecurityProtocolType.Tls;
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainInstallerForm());
        }
    }

    public class MainInstallerForm : Form
    {
        // Colores institucionales IPN / SiCAE
        private readonly Color ColorGuinda = Color.FromArgb(107, 29, 58);      // #6B1D3A
        private readonly Color ColorGuindaOscuro = Color.FromArgb(78, 18, 40); // #4E1228
        private readonly Color ColorDorado = Color.FromArgb(197, 155, 39);     // #C59B27
        private readonly Color ColorFondo = Color.FromArgb(246, 247, 249);
        private readonly Color ColorTarjeta = Color.White;
        private readonly Color ColorTexto = Color.FromArgb(33, 37, 41);
        private readonly Color ColorSubtexto = Color.FromArgb(100, 108, 120);
        private readonly Color ColorExito = Color.FromArgb(25, 135, 84);
        private readonly Color ColorAlerta = Color.FromArgb(180, 105, 14);
        private readonly Color ColorError = Color.FromArgb(200, 35, 51);

        private const string GITHUB_REPO_URL = "https://github.com/Emmanuel270114/Avance-SAE.git";
        private const string GITHUB_ZIP_MAIN = "https://github.com/Emmanuel270114/Avance-SAE/archive/refs/heads/main.zip";
        private const string GITHUB_ZIP_MASTER = "https://github.com/Emmanuel270114/Avance-SAE/archive/refs/heads/master.zip";
        private const string GTK3_DEFAULT_BIN = @"C:\Program Files\GTK3-Runtime Win64\bin";

        // Logo en Base64 embebido
        private const string LOGO_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAEMAAAA6CAYAAADr5+R6AAAOa0lEQVR4nO1baXBb1RX+niTLsmzLuy3v+x7HWZzF2UlCCBC2hAAdoIQOlKGUKbSl7Uz50WHa6bAMf/jFQMO+TGkpMYGwhOx2bCdxYjuOHe+25EXyvlvW8jrnvPdkJzgJRHLitJyMRtZb7/3uOd8595wTQRRFET8Ji0r6+knmHRgiKel1VFTVfAJCEARAECRQ/p/BEAQBQ9Z+OO0OCRQCyCXC5XIB4v8QGC6niz+ziUiTBXD2uzK8tO3XeOvpv8Pa0oGpCRsElQCVSgUI8nVzDIoG10BU6ktjTqsvqID2qnr0tHTAPmlDY1k1nHY7nw+NMyJpUSb8Qwwzrpc0x9sizKlrFSU1L/5wHwNSeP9WqGgishko19Bv29gEjr63F5Nj41i4ZRUS8tLZbLrOt6LzfCv8gwORd3Mh9EEBrCUCacyNAobL6WIAqr4pwd5X3+P53/XHXyBnwzL3uUvJ/tc/wYJNK2FMi3cfazldi4bjlUhZmou0FXlus7vcc+YNZwg0exGITI6D3uAPfVAgwhNj+Nisai6KcDqcvOprHtqGyq+LYbdNycdEJC/OxqbH74WlyYSKvYcZBG8C4blmiJDY/gorRCZAquGr1135kbIJtFTUos9sQcGdG/gdArEoW5iAU58fwsE3P0XG6sXY9ruf8/WKB/JEPINWkEC4LEGKInz9/RiImbgrARZN3jXjQ0LakLwkGyO9Axiy9EnX0T+XyPeFxkahtOhrfPf6J5gcGWcgvGHtVweGKL2YBk/qXHOg/JKXugeqBFUzjpO20KqqZnzot1qj5muy1y5FW+V5qNRq93mSuJxUPPjX3yOlIBe6QP10wHY9zESUV+idZ17EqaJDiEiOReF9t2DLk/dDFC/P9IoZVH5VjDNfHcPy7Zv5uMvpZA3z8fWFn8EfwcZwBuuNx/6CwIgQbHtuF6JS4uByOKHSqNHfYcWx9/nl+VtXI3FhBi+MAtbVyo++W5T9fJ+pG7WHT7Kr8wvU88Bs4xM8UTe+5FqdzgsCLuVUT1sXGsqqMdwzwCbkH2yALsAfToeDSbJ6fznefOIF1Bwsx6Hd/8H7v32ZgVRWruNcE7LWLYWl0cS/mVOuedAlSPZOQVBIDCQPvKn8LDIKF8HHz/fCoEgQWMWnCq0+3b/p8e2Iy01hmyd1n01IeygSDQgNQnejSTIhleS2h3sHULBqEfpN3fwMMhdPRXW1LlMfFIAHX3oW+VtXY90jd2LXa3+aVlN5+cg1Hnm3CCf3HJT2GaQg4jRfZK1Zwpox29YliUiddr4m7SC1v+MPjyJtZR5CYyNx85P34dDbezA2MMyA2m12JmatXochax9rPQ9JdE6CLpccVBW9uBsN5dUYHxzBbb95CEvv3MDnWd2Z9FRsbQ1lVcwpM+1eIcWBzh40llZj2d0bYW02s9kQEDGZSFiwcTlqDp3k6DRpcZbHkalHjCMqLpFWdBZMR2kVNWo2qTP7jqHuWAW7S/YgajWbU1h8FBy2KY5FLvYIClHTceKeiMRY+BkC8MpTTzOBknapNSpe2fEUPIJD0Fyi+sKgR+GM2599GBFxRqQtW4CdLzwlB0yHcfT9vWg+WeMm3KDIMNYQdsNyrKE8h0AQZnBPcHQ47tn1BCaGRvm3yyVCrdHcABu1S0i/2YK2ynq2dQLz8Nt74HQ68cw/X2GXSgDIUSVt0npaO3jz5piy49Duz5g/Gkor4XQQB4kIigpDdEaiR/HGnO1NRFnFlVwG/a1wRWhcFBbftgYbHr0b1tYOdtGNx6t4g0bnSQsUQiXC1Op0PMmyf32LjMJ8Ns30lfkMEoXtFOeQeBp4zVk+Q5BNRVDNGKCSwZJBUqvV2Pj4DtQdqYCPrxYJeRk48Oa/kZifibTleXzt1MQk4heko/54JbR+OiQuymSgSEtKPtoHc00Tlu/YjLC4KI81QzNXWtHd2M6qO5vQgCnkZi2JicSv3vsbJ3cWbV2DieExVH1bgq76NkQmxXKsMTEyjqnxSay6YCuDSEBL/CIy75BZzcyNXP3AvShOh5O/P3/5LfHPKx4UD7312QXHLxaXy8Uf62qneGrvYdFpd4gOu4PPdda3ik/GbBIf8V8uvrr9Wek6p/Qcl9MlOux2sfijL8Wqb4+LNQfLpfedL3+14uWEAKQvZn4R48OjFyMv8YbMHbSydIxMQePrw26YNIZMwNpk5sDOPjnFHCPfLm3nVQIajlcx2eZtXonOuhbWHE85Y068iSiKMNc08e7yhwyQVNME29gkIhKimRB7WsxIWpyN4g+/gMZXi3ue/yX0hgAJbBFwTE3h8DtFWL/rLmi0Pmg6UcOB3cIthR5t2OaEMwRBQHxumvu3QmwjvYO8+Vp4yyos2bYeowNDzBF1xaf5OgKDiHDjYzvQ32GBISoMax/exhGmpFHS3ubk54eRsWoRky5xSGpBDoqL9nHg5qv3mX/eRJwZGsvENjY4wiUBMgdDZCibhCEiFNogPVZt3wJDWDBf7rDZUVd8BrmbVnBSODwhWvI+Pho0V5xjM6GEsRL2kzY4XE7e50Qk+V21V5lD16r63t+U4H31fBECw4Mv2M0OjAwxEFRAAolWfHMM6YULMTVp410rCR3vbGxDS3U9bnroDjkyVaHXbEHVgVJEp8QjPMHokXu9thU1ERwtEhBKnsNi6oTWX+eeSHdbB+wuB4wp8bDZbMwZNLn2hhacrzqLdQ/cJgNJWTKB3q0mGDMTkb1mCT9jXkagl8uFKGZDKt7X34+I+Gg+bZscR+3ZGhTcupav04cY0DcyiNa2NpjMJqy/+1aJJ4gk1SqUHDyCrh4LmxxnTz30Jte81ioouU954MMTI4g0RsHhcKCsvBwLVy51h98jk2N4493dqK6qwuoNa+RcynQSM1NhiAlHXFL89LPne3nxYlG8eV9fHwIDAnmTVlZWhtzcXISFhVHAhZ6eHlgsFuTm5CA7O5uP0epTCM+xydQUOjo6kJCQcH0Twp6KMvi6ujr4+Pigv78fSUlJ0Ol06OzsxODgIE86IyMDAQEBOHHiBAoKCvgYAUdxBN1jNpuRn5/vNTCuuWaI8sD379+P0tJSpKenIzMzE+3t7XyONCMvLw96/XROMyQkBHv27MH69evdmkPAeKtecl3NhGRoaIjV3mAwQKvVMiikJYqQBtD506dPw8/PD6mpqaipqUFgYCADQlpB93gTkOtiJiT0WmXCzc3NrPZBQUFITEycNo2WlhYWui4lJQWK9Pb2wmq1wmg0IjQ0FN6U6wbGxULAmEwmdHV1MRikJSUlJdi5cyf/VsxrJjd4iyvmVRuTKIrMAUSihYWFMBqNqKioYOLkKpokyqMoJkHa5G0g5pVmkChDoUna7XbmBQLI25O+IcBQZC5W/YYxk4tFAUJpUbhWormSuoJ7I+Au7iq/5DyL+1s5pvRxXmpl+ZycEnM/Sy5ZyrVH/qJzyvGZ17nHJjevyA9y73suHuOVxnNNzMRht0Pj4/OjVf5Hm8gPTAIr6QH3Cv5QzbA2m/nGsHgjZ48owUKJGNp+D3RYudqu89ejp72Tu2go/zg5OoZgYzhXw6lnQ2pTovsoL0G7TeeUA93N7XyPVufLVTRdoD+CIkMlz1N5DLaJSR4k9Vwok57pOVAmfb7yLGeI1FqtxzEpmzR1sZwE9VxQ+ZKIk8oVNOlarQ9X3Gki7r5x6tngSpvI7UvUKkX9rcp4yOQoJ0HPp94NpQ2KSlLUa07tp6SpxsWL3T1W1LdOr6H8RPRY7XStw94o9ZlL7z1Z9CVfR2Mxm81SeVSl4laE6LR4aLWarh9XkvxJWZTFz56tZ+Nq5f8BpW1F2x7+xV4AAAAASUVORK5CYII=";

        // Respaldo embebido de requirements.txt (Windows 11) y requirements_w10.txt (Windows 10)
        private static readonly string EMBEDDED_REQ_W11 = string.Join("\r\n", new string[] {
            "alembic==1.16.5", "annotated-types==0.7.0", "anyio==4.10.0", "bcrypt==4.0.1", "brotli==1.2.0",
            "certifi==2026.5.20", "cffi==2.0.0", "charset-normalizer==3.4.7", "click==8.1.3", "colorama==0.4.6",
            "cryptography==49.0.0", "cssselect2==0.8.0", "dnspython==2.4.2", "email-validator==2.3.0",
            "exceptiongroup==1.3.1", "fastapi==0.116.1", "fonttools==4.60.2", "freetype-py==2.3.0",
            "greenlet==3.2.4", "h11==0.14.0", "html5lib==1.1", "idna==3.4", "itsdangerous==2.1.2",
            "Jinja2==3.1.2", "Mako==1.3.12", "MarkupSafe==2.1.3", "msal==1.37.0", "passlib==1.7.4",
            "pillow==11.3.0", "pycairo==1.28.0", "pycparser==2.23", "pydantic==2.13.4",
            "pydantic-settings==2.11.0", "pydantic_core==2.46.4", "pydyf==0.10.0", "PyJWT==2.13.0",
            "pyodbc==4.0.35", "pyphen==0.17.2", "python-dotenv==1.0.0", "python-multipart==0.0.6",
            "reportlab==4.0.0", "requests==2.31.0", "rlPyCairo==0.4.0", "six==1.17.0", "sniffio==1.3.1",
            "SQLAlchemy==2.0.32", "starlette==0.47.3", "tinycss2==1.4.0", "tomli==2.4.1",
            "typing-inspection==0.4.2", "typing_extensions==4.15.0", "urllib3==2.6.3", "uvicorn==0.22.0",
            "weasyprint==60.0", "webencodings==0.5.1", "xlsxwriter==3.2.9", "zopfli==0.2.3.post1"
        });

        private static readonly string EMBEDDED_REQ_W10 = string.Join("\r\n", new string[] {
            "alembic==1.16.5", "annotated-doc==0.0.4", "annotated-types==0.7.0", "anyio==4.10.0", "bcrypt==4.0.1",
            "brotli==1.2.0", "certifi==2026.5.20", "cffi==2.0.0", "charset-normalizer==3.4.7", "click==8.1.3",
            "colorama==0.4.6", "cryptography==49.0.0", "cssselect2==0.8.0", "dnspython==2.4.2",
            "email-validator==2.3.0", "exceptiongroup==1.3.1", "fastapi==0.116.1", "fonttools==4.60.2",
            "freetype-py==2.3.0", "greenlet==3.2.4", "h11==0.14.0", "html5lib==1.1", "idna==3.4",
            "itsdangerous==2.1.2", "Jinja2==3.1.2", "Mako==1.3.12", "MarkupSafe==2.1.3", "msal==1.37.0",
            "passlib==1.7.4", "pillow==11.3.0", "pycairo==1.28.0", "pycparser==2.23", "pydantic==2.13.4",
            "pydantic-settings==2.11.0", "pydantic_core==2.46.4", "pydyf==0.10.0", "PyJWT==2.13.0",
            "pyodbc==5.3.0", "pyphen==0.17.2", "python-dotenv==1.0.0", "python-multipart==0.0.6",
            "reportlab==4.0.0", "requests==2.31.0", "rlPyCairo==0.4.0", "six==1.17.0", "sniffio==1.3.1",
            "SQLAlchemy==2.0.32", "starlette==0.40.0", "tinycss2==1.4.0", "tinyhtml5==2.1.0",
            "tomli==2.4.1", "typing-inspection==0.4.2", "typing_extensions==4.15.0", "urllib3==2.6.3",
            "uvicorn==0.22.0", "weasyprint==60.0", "webencodings==0.5.1", "xlsxwriter==3.2.9", "zopfli==0.2.3.post1"
        });

        // Estado del Wizard
        private int currentStep = 0; // 0: SO, 1: Requisitos, 2: Dependencias y Ruta, 3: Instalación
        private bool isInstalling = false;
        private bool installSuccess = false;

        // Datos detectados
        private string detectedPythonExe = "";
        private string detectedPythonVersion = "";
        private bool pythonVersionCompatible = false;
        private string incompatiblePythonFound = "";
        private string detectedGitExe = "";
        private bool odbcInstalled = false;
        private bool gtkInstalled = false;
        private bool gtkInPath = false;
        private string gtkBinFoundPath = GTK3_DEFAULT_BIN;

        // URLs directas oficiales de las versiones exactas requeridas
        private const string URL_PYTHON_310_EXE = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe";
        private const string URL_PYTHON_39_EXE = "https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe";
        private const string URL_GIT_WIN64_EXE = "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe";
        private const string URL_ODBC17_MSI = "https://go.microsoft.com/fwlink/?linkid=2249004";
        private const string URL_GTK3_WIN64_EXE = "https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases/download/2022-01-04/gtk3-runtime-3.24.31-2022-01-04-ts-win64.exe";

        // Controles principales
        private Label lblStepIndicator;
        private Panel pnlContentHost;
        private Panel[] stepPanels = new Panel[4];
        private Button btnBack;
        private Button btnNext;
        private Button btnCancel;

        // Paso 1: Selección de SO
        private Panel cardW11;
        private Panel cardW10;
        private RadioButton rbWin11;
        private RadioButton rbWin10;
        private Label lblSelectedReqSummary;

        // Paso 2: Verificación de Requisitos
        private Label lblStatusPython;
        private Label lblStatusGit;
        private Label lblStatusOdbc;
        private Label lblStatusGtk;
        private Button btnFixGtkPath;

        // Paso 3: Dependencias y Destino
        private Label lblStep3OsBadge;
        private TextBox txtInstallDir;
        private RadioButton rbSourceGithub;
        private RadioButton rbSourceLocal;
        private CheckBox chkDesktopBat;
        private CheckBox chkAcceptDeps;

        // Paso 4: Progreso y Consola
        private ProgressBar progressBar;
        private Label lblProgressStatus;
        private RichTextBox rtbLog;
        private Panel pnlFinishActions;
        private Button btnLaunchNow;
        private Button btnOpenFolder;

        public MainInstallerForm()
        {
            InitializeComponent();
            DetectCurrentOSAndSuggest();
            ShowStep(0);
        }

        private void InitializeComponent()
        {
            this.Text = "Instalador Oficial SiCAE - Sistema de Captura y Análisis de la Estadística (IPN)";
            this.Size = new Size(880, 705);
            this.MinimumSize = new Size(880, 705);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.BackColor = ColorFondo;
            this.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);
            this.FormBorderStyle = FormBorderStyle.FixedSingle;
            this.MaximizeBox = false;

            try
            {
                this.Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
            }
            catch { }

            // === ENCABEZADO SUPERIOR ===
            Panel pnlHeader = new Panel
            {
                Dock = DockStyle.Top,
                Height = 82,
                BackColor = ColorGuinda
            };

            PictureBox picLogo = new PictureBox
            {
                Location = new Point(22, 13),
                Size = new Size(62, 54),
                SizeMode = PictureBoxSizeMode.Zoom,
                BackColor = Color.White
            };
            try
            {
                using (Stream resStream = System.Reflection.Assembly.GetExecutingAssembly().GetManifestResourceStream("sicae_header.png"))
                {
                    if (resStream != null)
                    {
                        picLogo.Image = new Bitmap(Image.FromStream(resStream));
                    }
                }
            }
            catch { }
            pnlHeader.Controls.Add(picLogo);

            Label lblTitle = new Label
            {
                Text = "Asistente de Instalación de SiCAE",
                Font = new Font("Segoe UI", 16f, FontStyle.Bold),
                ForeColor = Color.White,
                AutoSize = true,
                Location = new Point(102, 14)
            };
            pnlHeader.Controls.Add(lblTitle);

            Label lblSubtitle = new Label
            {
                Text = "Sistema de Captura y Análisis de la Estadística • Instituto Politécnico Nacional",
                Font = new Font("Segoe UI", 9.5f, FontStyle.Regular),
                ForeColor = Color.FromArgb(240, 225, 230),
                AutoSize = true,
                Location = new Point(104, 46)
            };
            pnlHeader.Controls.Add(lblSubtitle);

            lblStepIndicator = new Label
            {
                Text = "Paso 1 de 4",
                Font = new Font("Segoe UI", 10f, FontStyle.Bold),
                ForeColor = ColorDorado,
                AutoSize = false,
                TextAlign = ContentAlignment.MiddleRight,
                Size = new Size(160, 30),
                Location = new Point(690, 26)
            };
            pnlHeader.Controls.Add(lblStepIndicator);

            Panel pnlGoldBar = new Panel
            {
                Dock = DockStyle.Bottom,
                Height = 4,
                BackColor = ColorDorado
            };
            pnlHeader.Controls.Add(pnlGoldBar);

            // === BARRA INFERIOR DE NAVEGACIÓN ===
            Panel pnlFooter = new Panel
            {
                Dock = DockStyle.Bottom,
                Height = 64,
                BackColor = Color.White
            };
            Panel pnlFooterLine = new Panel
            {
                Dock = DockStyle.Top,
                Height = 1,
                BackColor = Color.FromArgb(220, 224, 230)
            };
            pnlFooter.Controls.Add(pnlFooterLine);

            btnCancel = new Button
            {
                Text = "Cancelar",
                Size = new Size(110, 36),
                Location = new Point(24, 14),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(242, 244, 247),
                ForeColor = ColorTexto,
                Cursor = Cursors.Hand
            };
            btnCancel.FlatAppearance.BorderColor = Color.FromArgb(200, 205, 212);
            btnCancel.Click += (s, e) =>
            {
                if (isInstalling)
                {
                    MessageBox.Show("La instalación está en curso. Espere a que termine el proceso actual.", "Instalación en progreso", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    return;
                }
                if (installSuccess || MessageBox.Show("¿Deseas salir del asistente de instalación de SiCAE?", "Confirmar salida", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
                {
                    Application.Exit();
                }
            };
            pnlFooter.Controls.Add(btnCancel);

            btnBack = new Button
            {
                Text = "← Anterior",
                Size = new Size(125, 36),
                Location = new Point(565, 14),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.White,
                ForeColor = ColorTexto,
                Cursor = Cursors.Hand
            };
            btnBack.FlatAppearance.BorderColor = Color.FromArgb(190, 195, 202);
            btnBack.Click += BtnBack_Click;
            pnlFooter.Controls.Add(btnBack);

            btnNext = new Button
            {
                Text = "Siguiente →",
                Size = new Size(145, 36),
                Location = new Point(700, 14),
                FlatStyle = FlatStyle.Flat,
                BackColor = ColorGuinda,
                ForeColor = Color.White,
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
                Cursor = Cursors.Hand
            };
            btnNext.FlatAppearance.BorderSize = 0;
            btnNext.Click += BtnNext_Click;
            pnlFooter.Controls.Add(btnNext);

            // === CONTENEDOR CENTRAL ===
            pnlContentHost = new Panel
            {
                Dock = DockStyle.Fill,
                Padding = new Padding(24, 18, 24, 18),
                BackColor = ColorFondo
            };

            this.Controls.Add(pnlContentHost);
            this.Controls.Add(pnlFooter);
            this.Controls.Add(pnlHeader);

            BuildStep0_OSSelection();
            BuildStep1_Prerequisites();
            BuildStep2_DependenciesAndPath();
            BuildStep3_InstallationProgress();

            foreach (Panel p in stepPanels)
            {
                p.Dock = DockStyle.Fill;
                p.Visible = false;
                pnlContentHost.Controls.Add(p);
            }
        }

        // =========================================================================
        // PASO 1: BIENVENIDA Y SELECCIÓN DE SISTEMA OPERATIVO (W10 / W11)
        // =========================================================================
        private void BuildStep0_OSSelection()
        {
            Panel pnl = new Panel { BackColor = ColorFondo };

            Label lblWelcome = new Label
            {
                Text = "¡Bienvenido(a)! Configuremos SiCAE en tu computadora",
                Font = new Font("Segoe UI", 14f, FontStyle.Bold),
                ForeColor = ColorGuinda,
                AutoSize = true,
                Location = new Point(4, 2)
            };
            pnl.Controls.Add(lblWelcome);

            Label lblIntro = new Label
            {
                Text = "Este asistente te guiará paso a paso de forma sencilla para descargar el proyecto oficial de GitHub,\r\n" +
                       "crear su entorno virtual de Python, instalar sus librerías y dejar un acceso rápido en tu Escritorio.",
                Font = new Font("Segoe UI", 9.75f),
                ForeColor = ColorTexto,
                AutoSize = true,
                Location = new Point(6, 34)
            };
            pnl.Controls.Add(lblIntro);

            // Banner de advertencia de SO exclusivo
            Panel pnlWarning = CreateCardPanel(new Point(6, 84), new Size(812, 68), Color.FromArgb(255, 248, 230), Color.FromArgb(235, 190, 90));
            Label lblWarnTitle = new Label
            {
                Text = "⚠️ AVISO IMPORTANTE DE COMPATIBILIDAD DE SISTEMA OPERATIVO",
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
                ForeColor = Color.FromArgb(145, 80, 0),
                AutoSize = true,
                Location = new Point(14, 10)
            };
            Label lblWarnText = new Label
            {
                Text = "Por el momento, el proyecto SiCAE únicamente se puede instalar y ejecutar en computadoras con Windows 10 y Windows 11 (64 bits).\r\n" +
                       "Otros sistemas operativos (Windows 7/8, macOS o distribuciones Linux) no están soportados actualmente por este instalador.",
                Font = new Font("Segoe UI", 9f),
                ForeColor = Color.FromArgb(115, 65, 5),
                AutoSize = true,
                Location = new Point(14, 31)
            };
            pnlWarning.Controls.Add(lblWarnTitle);
            pnlWarning.Controls.Add(lblWarnText);
            pnl.Controls.Add(pnlWarning);

            Label lblChooseOS = new Label
            {
                Text = "1. Selecciona el Sistema Operativo donde vas a instalar SiCAE:",
                Font = new Font("Segoe UI", 11f, FontStyle.Bold),
                ForeColor = ColorTexto,
                AutoSize = true,
                Location = new Point(6, 168)
            };
            pnl.Controls.Add(lblChooseOS);

            // Tarjeta Windows 11
            cardW11 = CreateCardPanel(new Point(6, 200), new Size(396, 175), Color.White, Color.FromArgb(210, 215, 222));
            cardW11.Cursor = Cursors.Hand;
            rbWin11 = new RadioButton
            {
                Text = "  Windows 11 (64 bits)",
                Font = new Font("Segoe UI", 12f, FontStyle.Bold),
                ForeColor = ColorGuinda,
                AutoSize = true,
                AutoCheck = false,
                Location = new Point(18, 16),
                Cursor = Cursors.Hand
            };
            Label lblW11Desc = new Label
            {
                Text = "• Archivo a instalar: requirements.txt\r\n" +
                       "• Conector SQL Server: pyodbc == 4.0.35\r\n" +
                       "• Motor Web: FastAPI 0.116.1 + Starlette 0.47.3\r\n" +
                       "• Motor de Oficios PDF: WeasyPrint 60.0 + PyCairo 1.28\r\n" +
                       "• Optimizado para librerías nativas de Windows 11.",
                Font = new Font("Segoe UI", 9.1f),
                ForeColor = ColorSubtexto,
                AutoSize = false,
                Size = new Size(360, 108),
                Location = new Point(20, 52),
                Cursor = Cursors.Hand
            };
            cardW11.Controls.Add(rbWin11);
            cardW11.Controls.Add(lblW11Desc);
            pnl.Controls.Add(cardW11);

            // Tarjeta Windows 10
            cardW10 = CreateCardPanel(new Point(422, 200), new Size(396, 175), Color.White, Color.FromArgb(210, 215, 222));
            cardW10.Cursor = Cursors.Hand;
            rbWin10 = new RadioButton
            {
                Text = "  Windows 10 (64 bits)",
                Font = new Font("Segoe UI", 12f, FontStyle.Bold),
                ForeColor = ColorGuinda,
                AutoSize = true,
                AutoCheck = false,
                Location = new Point(18, 16),
                Cursor = Cursors.Hand
            };
            Label lblW10Desc = new Label
            {
                Text = "• Archivo a instalar: requirements_w10.txt\r\n" +
                       "• Conector SQL Server: pyodbc == 5.3.0\r\n" +
                       "• Motor Web: FastAPI 0.116.1 + Starlette 0.40.0\r\n" +
                       "• Motor de Oficios PDF: WeasyPrint 60.0 + tinyhtml5 2.1.0\r\n" +
                       "• Adaptado para compatibilidad en Windows 10.",
                Font = new Font("Segoe UI", 9.1f),
                ForeColor = ColorSubtexto,
                AutoSize = false,
                Size = new Size(360, 108),
                Location = new Point(20, 52),
                Cursor = Cursors.Hand
            };
            cardW10.Controls.Add(rbWin10);
            cardW10.Controls.Add(lblW10Desc);
            pnl.Controls.Add(cardW10);

            // Resumen dinámico inferior
            Panel pnlSummary = CreateCardPanel(new Point(6, 390), new Size(812, 74), Color.FromArgb(240, 244, 248), Color.FromArgb(200, 210, 222));
            lblSelectedReqSummary = new Label
            {
                Text = "",
                Font = new Font("Segoe UI", 9.5f, FontStyle.Regular),
                ForeColor = ColorTexto,
                AutoSize = false,
                Size = new Size(784, 54),
                Location = new Point(14, 10)
            };
            pnlSummary.Controls.Add(lblSelectedReqSummary);
            pnl.Controls.Add(pnlSummary);

            rbWin11.Click += (s, e) => SelectTargetOS(true);
            lblW11Desc.Click += (s, e) => SelectTargetOS(true);
            cardW11.Click += (s, e) => SelectTargetOS(true);

            rbWin10.Click += (s, e) => SelectTargetOS(false);
            lblW10Desc.Click += (s, e) => SelectTargetOS(false);
            cardW10.Click += (s, e) => SelectTargetOS(false);

            stepPanels[0] = pnl;
        }

        private void SelectTargetOS(bool chooseWin11)
        {
            rbWin11.Checked = chooseWin11;
            rbWin10.Checked = !chooseWin11;

            if (cardW11 != null && cardW10 != null)
            {
                cardW11.BackColor = chooseWin11 ? Color.FromArgb(253, 245, 248) : Color.White;
                cardW10.BackColor = !chooseWin11 ? Color.FromArgb(253, 245, 248) : Color.White;
                cardW11.Invalidate();
                cardW10.Invalidate();
            }

            UpdateOSSelectionUI();
        }

        private int GetRealWindowsBuild()
        {
            try
            {
                using (RegistryKey key = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Windows NT\CurrentVersion"))
                {
                    if (key != null)
                    {
                        object val = key.GetValue("CurrentBuildNumber") ?? key.GetValue("CurrentBuild");
                        if (val != null)
                        {
                            int b;
                            if (int.TryParse(val.ToString(), out b))
                                return b;
                        }
                    }
                }
            }
            catch { }
            return Environment.OSVersion.Version.Build;
        }

        private void DetectCurrentOSAndSuggest()
        {
            // Iniciar sin preseleccionar para que el usuario elija explícitamente Windows 10 o Windows 11
            rbWin11.Checked = false;
            rbWin10.Checked = false;
            UpdateOSSelectionUI();
        }

        private void UpdateOSSelectionUI()
        {
            int build = GetRealWindowsBuild();
            string detectedName = (build >= 22000) ? "Windows 11" : "Windows 10";

            if (!rbWin11.Checked && !rbWin10.Checked)
            {
                lblSelectedReqSummary.Text = string.Format(
                    "💻 Sistema detectado en este equipo: {0} (Compilación {1})\r\n" +
                    "👆 Por favor haz clic arriba en 'Windows 11' o 'Windows 10' para elegir qué versión instalar.",
                    detectedName, build);
                return;
            }

            string chosenOS = rbWin11.Checked ? "Windows 11" : "Windows 10";
            string chosenFile = rbWin11.Checked ? "requirements.txt" : "requirements_w10.txt";

            lblSelectedReqSummary.Text = string.Format(
                "💻 Sistema detectado en este equipo: {0} (Compilación {1})\r\n" +
                "✅ Selección actual: {2}  →  El instalador utilizará el archivo \"{3}\" para configurar el entorno virtual.",
                detectedName, build, chosenOS, chosenFile);

            if (lblStep3OsBadge != null)
            {
                lblStep3OsBadge.Text = string.Format("SO: {0} ({1})", chosenOS, chosenFile);
            }
        }

        // =========================================================================
        // PASO 2: VERIFICACIÓN DE REQUISITOS EXTERNOS DEL SISTEMA Y GUÍA PASO A PASO
        // =========================================================================
        private void BuildStep1_Prerequisites()
        {
            Panel pnl = new Panel { BackColor = ColorFondo };

            Label lblTitle = new Label
            {
                Text = "2. Verificación e Instalación Guiada de Requisitos",
                Font = new Font("Segoe UI", 14f, FontStyle.Bold),
                ForeColor = ColorGuinda,
                AutoSize = true,
                Location = new Point(4, 2)
            };
            pnl.Controls.Add(lblTitle);

            Label lblDesc = new Label
            {
                Text = "SiCAE requiere versiones específicas de estos 4 componentes. Haz clic en el botón de cada requisito a la derecha\r\n" +
                       "para ver su Guía Paso a Paso e instalar la versión exacta requerida directamente desde este asistente:",
                Font = new Font("Segoe UI", 9.3f),
                ForeColor = ColorTexto,
                AutoSize = true,
                Location = new Point(6, 32)
            };
            pnl.Controls.Add(lblDesc);

            // 1. Python (Específicamente 3.9, 3.10 o 3.11 de 64 bits)
            Panel cardPy = CreatePrereqRow(
                new Point(6, 82),
                "1. Python 3.9, 3.10 o 3.11 (64 bits) — [Versión específica requerida]",
                "Requerido entre 3.9 y 3.11 (Python 3.12+ NO es compatible con pyodbc 4.0.35 ni MarkupSafe 2.1.3).",
                out lblStatusPython,
                "📖 Paso a Paso / Instalar",
                (s, e) => OpenPrereqGuide("PYTHON")
            );
            pnl.Controls.Add(cardPy);

            // 2. Git
            Panel cardGit = CreatePrereqRow(
                new Point(6, 170),
                "2. Git para Windows 64 bits (v2.47+ Recomendado para GitHub)",
                "Se ocupa para clonar el repositorio Avance-SAE y descargar actualizaciones con git pull.",
                out lblStatusGit,
                "📖 Paso a Paso / Instalar",
                (s, e) => OpenPrereqGuide("GIT")
            );
            pnl.Controls.Add(cardGit);

            // 3. ODBC Driver 17
            Panel cardOdbc = CreatePrereqRow(
                new Point(6, 258),
                "3. Microsoft ODBC Driver 17 for SQL Server (64 bits) — [Versión 17 exacta]",
                "El sistema exige específicamente la versión 17 (definida en .env como 'ODBC Driver 17 for SQL Server').",
                out lblStatusOdbc,
                "📖 Paso a Paso / Instalar",
                (s, e) => OpenPrereqGuide("ODBC17")
            );
            pnl.Controls.Add(cardOdbc);

            // 4. GTK3 Runtime + PATH
            Panel cardGtk = CreateCardPanel(new Point(6, 346), new Size(812, 92), Color.White, Color.FromArgb(215, 220, 228));
            Label lblGtkTitle = new Label
            {
                Text = "4. GTK3 Runtime Win64 (v3.24.31) + Variable PATH — [Requerido por WeasyPrint 60.0]",
                Font = new Font("Segoe UI", 10f, FontStyle.Bold),
                ForeColor = ColorTexto,
                AutoSize = false,
                Size = new Size(575, 20),
                Location = new Point(14, 8)
            };
            Label lblGtkSub = new Label
            {
                Text = "Instala las librerías C (.dll) en C:\\Program Files\\GTK3-Runtime Win64\\bin para generar oficios en PDF.",
                Font = new Font("Segoe UI", 8.8f),
                ForeColor = ColorSubtexto,
                AutoSize = false,
                Size = new Size(575, 20),
                Location = new Point(14, 30)
            };
            lblStatusGtk = new Label
            {
                Text = "Verificando...",
                Font = new Font("Segoe UI", 9f, FontStyle.Bold),
                AutoSize = false,
                AutoEllipsis = true,
                Size = new Size(575, 32),
                Location = new Point(14, 52)
            };
            Button btnDlGtk = new Button
            {
                Text = "📖 Paso a Paso / Instalar",
                Size = new Size(195, 30),
                Location = new Point(602, 12),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(242, 244, 248),
                Font = new Font("Segoe UI", 8.5f, FontStyle.Bold),
                ForeColor = ColorGuindaOscuro,
                Cursor = Cursors.Hand
            };
            btnDlGtk.Click += (s, e) => OpenPrereqGuide("GTK3");

            btnFixGtkPath = new Button
            {
                Text = "⚡ Configurar PATH Automático",
                Size = new Size(195, 30),
                Location = new Point(602, 50),
                FlatStyle = FlatStyle.Flat,
                BackColor = ColorGuinda,
                ForeColor = Color.White,
                Font = new Font("Segoe UI", 8.5f, FontStyle.Bold),
                Cursor = Cursors.Hand
            };
            btnFixGtkPath.FlatAppearance.BorderSize = 0;
            btnFixGtkPath.Click += BtnFixGtkPath_Click;

            cardGtk.Controls.Add(lblGtkTitle);
            cardGtk.Controls.Add(lblGtkSub);
            cardGtk.Controls.Add(lblStatusGtk);
            cardGtk.Controls.Add(btnDlGtk);
            cardGtk.Controls.Add(btnFixGtkPath);
            pnl.Controls.Add(cardGtk);

            Button btnRefresh = new Button
            {
                Text = "🔄 Volver a verificar requisitos del sistema",
                Size = new Size(280, 34),
                Location = new Point(6, 446),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.White,
                ForeColor = ColorGuinda,
                Font = new Font("Segoe UI", 9f, FontStyle.Bold),
                Cursor = Cursors.Hand
            };
            btnRefresh.Click += (s, e) => RunPrerequisitesCheck();
            pnl.Controls.Add(btnRefresh);

            stepPanels[1] = pnl;
        }

        private Panel CreatePrereqRow(Point loc, string title, string desc, out Label statusLabel, string btnText, EventHandler onBtnClick)
        {
            Panel card = CreateCardPanel(loc, new Size(812, 80), Color.White, Color.FromArgb(215, 220, 228));
            Label lblT = new Label
            {
                Text = title,
                Font = new Font("Segoe UI", 10f, FontStyle.Bold),
                ForeColor = ColorTexto,
                AutoSize = false,
                Size = new Size(580, 20),
                Location = new Point(14, 7)
            };
            Label lblD = new Label
            {
                Text = desc,
                Font = new Font("Segoe UI", 8.6f),
                ForeColor = ColorSubtexto,
                AutoSize = false,
                AutoEllipsis = true,
                Size = new Size(580, 20),
                Location = new Point(14, 29)
            };
            statusLabel = new Label
            {
                Text = "Verificando...",
                Font = new Font("Segoe UI", 9f, FontStyle.Bold),
                AutoSize = false,
                AutoEllipsis = true,
                Size = new Size(580, 22),
                Location = new Point(14, 51)
            };
            Button btn = new Button
            {
                Text = btnText,
                Size = new Size(195, 32),
                Location = new Point(602, 24),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(242, 244, 248),
                Font = new Font("Segoe UI", 8.5f, FontStyle.Bold),
                ForeColor = ColorGuindaOscuro,
                Cursor = Cursors.Hand
            };
            btn.Click += onBtnClick;

            card.Controls.Add(lblT);
            card.Controls.Add(lblD);
            card.Controls.Add(statusLabel);
            card.Controls.Add(btn);
            return card;
        }

        private void OpenPrereqGuide(string reqType)
        {
            using (PrerequisiteGuideDialog dlg = new PrerequisiteGuideDialog(reqType, this.Icon))
            {
                dlg.ShowDialog(this);
            }
            // Al cerrar la guía, re-verificar automáticamente el estado de todos los requisitos
            RunPrerequisitesCheck();
        }

        private void RunPrerequisitesCheck()
        {
            // 1. Buscar Python compatible (3.9, 3.10 o 3.11 de 64 bits)
            detectedPythonExe = FindPythonExecutable(out detectedPythonVersion);
            if (!string.IsNullOrEmpty(detectedPythonExe) && pythonVersionCompatible)
            {
                lblStatusPython.Text = "✅ Compatible: " + detectedPythonVersion + " (" + detectedPythonExe + ")";
                lblStatusPython.ForeColor = ColorExito;
            }
            else if (!string.IsNullOrEmpty(incompatiblePythonFound))
            {
                lblStatusPython.Text = "⚠️ Detectado " + incompatiblePythonFound + " (NO compatible). Pulsa 'Paso a Paso / Instalar' para instalar Python 3.10.";
                lblStatusPython.ForeColor = ColorError;
            }
            else
            {
                lblStatusPython.Text = "❌ No detectado. Pulsa 'Paso a Paso / Instalar' a la derecha para instalar Python 3.10.11.";
                lblStatusPython.ForeColor = ColorError;
            }

            // 2. Buscar Git
            detectedGitExe = FindGitExecutable();
            if (!string.IsNullOrEmpty(detectedGitExe))
            {
                lblStatusGit.Text = "✅ Detectado: Git disponible (" + detectedGitExe + ")";
                lblStatusGit.ForeColor = ColorExito;
            }
            else
            {
                lblStatusGit.Text = "⚠️ No detectado. Pulsa 'Paso a Paso / Instalar' (o el instalador bajará el ZIP de GitHub).";
                lblStatusGit.ForeColor = ColorAlerta;
            }

            // 3. Verificar ODBC Driver 17
            odbcInstalled = CheckOdbcDriver17();
            if (odbcInstalled)
            {
                lblStatusOdbc.Text = "✅ Detectado: Microsoft ODBC Driver 17 for SQL Server (64 bits) instalado.";
                lblStatusOdbc.ForeColor = ColorExito;
            }
            else
            {
                lblStatusOdbc.Text = "❌ No detectado: Pulsa 'Paso a Paso / Instalar' para instalar ODBC Driver 17.";
                lblStatusOdbc.ForeColor = ColorAlerta;
            }

            // 4. Verificar GTK3 Runtime y PATH
            CheckGtkStatus();
            if (gtkInstalled && gtkInPath)
            {
                lblStatusGtk.Text = "✅ Detectado: GTK3 Runtime instalado y registrado en el PATH (" + gtkBinFoundPath + ").";
                lblStatusGtk.ForeColor = ColorExito;
            }
            else if (gtkInstalled && !gtkInPath)
            {
                lblStatusGtk.Text = "⚠️ GTK3 instalado pero falta en PATH. Pulsa '⚡ Configurar PATH Automático'.";
                lblStatusGtk.ForeColor = ColorAlerta;
            }
            else
            {
                lblStatusGtk.Text = "❌ No detectado. Pulsa 'Paso a Paso / Instalar' para instalar GTK3 Runtime 3.24.31.";
                lblStatusGtk.ForeColor = ColorAlerta;
            }
        }

        private void BtnFixGtkPath_Click(object sender, EventArgs e)
        {
            string targetBin = Directory.Exists(gtkBinFoundPath) ? gtkBinFoundPath : GTK3_DEFAULT_BIN;
            bool ok = EnsureDirectoryInUserPath(targetBin);
            CheckGtkStatus();
            RunPrerequisitesCheck();

            if (ok)
            {
                MessageBox.Show(
                    "Se agregó correctamente la ruta:\r\n" + targetBin + "\r\n\r\n" +
                    "a la variable de entorno PATH del usuario y a la sesión actual.\r\n" +
                    "Además, el script Iniciar_SiCAE.bat también la cargará automáticamente al arrancar el servidor.",
                    "PATH de GTK3 Configurado",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Information);
            }
        }

        // =========================================================================
        // PASO 3: ADVERTENCIA DE DEPENDENCIAS A INSTALAR + RUTA DEL PROYECTO
        // =========================================================================
        private void BuildStep2_DependenciesAndPath()
        {
            Panel pnl = new Panel { BackColor = ColorFondo };

            Label lblTitle = new Label
            {
                Text = "3. Dependencias que se instalarán y Ubicación del Proyecto",
                Font = new Font("Segoe UI", 13.5f, FontStyle.Bold),
                ForeColor = ColorGuinda,
                AutoSize = true,
                Location = new Point(4, 0)
            };
            pnl.Controls.Add(lblTitle);

            lblStep3OsBadge = new Label
            {
                Text = "SO: Windows 11 (requirements.txt)",
                Font = new Font("Segoe UI", 9f, FontStyle.Bold),
                ForeColor = ColorGuindaOscuro,
                AutoSize = false,
                TextAlign = ContentAlignment.MiddleRight,
                Size = new Size(303, 20),
                Location = new Point(515, 4)
            };
            pnl.Controls.Add(lblStep3OsBadge);

            Label lblSub = new Label
            {
                Text = "Por transparencia y seguridad, revisa todo lo que se instalará en el entorno virtual (venv) y para qué lo ocupa SiCAE:",
                Font = new Font("Segoe UI", 9.2f),
                ForeColor = ColorTexto,
                AutoSize = true,
                Location = new Point(6, 26)
            };
            pnl.Controls.Add(lblSub);

            // Cuadro informativo de dependencias y para qué se ocupan
            RichTextBox rtbDeps = new RichTextBox
            {
                Location = new Point(6, 50),
                Size = new Size(812, 200),
                ReadOnly = true,
                BackColor = Color.White,
                BorderStyle = BorderStyle.FixedSingle,
                Font = new Font("Segoe UI", 9.1f),
                ScrollBars = RichTextBoxScrollBars.Vertical
            };
            rtbDeps.Text =
                "▸ 1. SERVIDOR Y PLATAFORMA WEB (FastAPI 0.116.1, Uvicorn 0.22.0, Starlette, Jinja2, python-multipart, AnyIO)\r\n" +
                "   • ¿Para qué lo ocupa SiCAE?: Levanta el servidor web en tu equipo (puerto 50000), procesa las peticiones HTTP y dibuja las pantallas HTML del sistema.\r\n\r\n" +
                "▸ 2. CONEXIÓN A BASE DE DATOS SQL SERVER (SQLAlchemy 2.0.32, pyodbc [4.0.35 en W11 / 5.3.0 en W10], Alembic, Greenlet)\r\n" +
                "   • ¿Para qué lo ocupa SiCAE?: Conecta de forma segura con Microsoft SQL Server para consultar y almacenar Matrícula, Aprovechamiento, Egresados, Titulados y Catálogos.\r\n\r\n" +
                "▸ 3. GENERACIÓN DE OFICIOS Y ACUSES EN PDF (WeasyPrint 60.0, ReportLab 4.0, PyCairo 1.28, rlPyCairo, Pillow, FontTools, PyDyf)\r\n" +
                "   • ¿Para qué lo ocupa SiCAE?: Convierte las plantillas institucionales (SEP / IPN) en los Acuses Oficiales de Conclusión de Captura en PDF listos para firma e impresión.\r\n\r\n" +
                "▸ 4. EXPORTACIÓN DE REPORTES ESTADÍSTICOS EN EXCEL (XlsxWriter 3.2.9)\r\n" +
                "   • ¿Para qué lo ocupa SiCAE?: Permite exportar y descargar sábanas de datos y reportes estadísticos en archivos de Excel (.xlsx).\r\n\r\n" +
                "▸ 5. CORREO INSTITUCIONAL MICROSOFT GRAPH (MSAL 1.37.0, Requests, email-validator, dnspython, Certifi)\r\n" +
                "   • ¿Para qué lo ocupa SiCAE?: Autentica con Microsoft Entra ID / Exchange Online para enviar correos desde sicae@ipn.mx (recuperación de contraseñas y acuses PDF).\r\n\r\n" +
                "▸ 6. SEGURIDAD, SESIONES Y CONFIGURACIÓN (Bcrypt 4.0.1, Passlib, PyJWT, Cryptography, Pydantic 2.13, python-dotenv)\r\n" +
                "   • ¿Para qué lo ocupa SiCAE?: Encripta las contraseñas de los usuarios, firma digitalmente las cookies de sesión (device_id / session_id) y carga las variables del archivo .env.";
            pnl.Controls.Add(rtbDeps);

            // Panel de Carpeta Destino y Origen GitHub
            Panel pnlConfig = CreateCardPanel(new Point(6, 258), new Size(812, 168), Color.White, Color.FromArgb(210, 215, 222));

            Label lblFolder = new Label
            {
                Text = "📂 Carpeta donde se instalará el proyecto SiCAE (y a donde apuntará el script .bat):",
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
                ForeColor = ColorTexto,
                AutoSize = true,
                Location = new Point(14, 10)
            };
            pnlConfig.Controls.Add(lblFolder);

            string desktopDir = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            string defaultTarget = Path.Combine(desktopDir, "Avance-SAE");

            txtInstallDir = new TextBox
            {
                Text = defaultTarget,
                Font = new Font("Segoe UI", 9.5f),
                Location = new Point(14, 34),
                Size = new Size(660, 26)
            };
            pnlConfig.Controls.Add(txtInstallDir);

            Button btnBrowse = new Button
            {
                Text = "Examinar...",
                Size = new Size(115, 27),
                Location = new Point(682, 33),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(242, 244, 248),
                Cursor = Cursors.Hand
            };
            btnBrowse.Click += (s, e) =>
            {
                using (FolderBrowserDialog fbd = new FolderBrowserDialog())
                {
                    fbd.Description = "Selecciona la carpeta donde deseas instalar SiCAE (ej. en tu Escritorio)";
                    fbd.SelectedPath = txtInstallDir.Text;
                    if (fbd.ShowDialog() == DialogResult.OK)
                    {
                        string selected = fbd.SelectedPath;
                        if (!selected.EndsWith("Avance-SAE", StringComparison.OrdinalIgnoreCase) &&
                            !selected.EndsWith("SiCAE", StringComparison.OrdinalIgnoreCase) &&
                            !File.Exists(Path.Combine(selected, "requirements.txt")))
                        {
                            selected = Path.Combine(selected, "Avance-SAE");
                        }
                        txtInstallDir.Text = selected;
                    }
                }
            };
            pnlConfig.Controls.Add(btnBrowse);

            Label lblOrigin = new Label
            {
                Text = "🌐 Origen de los archivos del proyecto:",
                Font = new Font("Segoe UI", 9.2f, FontStyle.Bold),
                ForeColor = ColorTexto,
                AutoSize = true,
                Location = new Point(14, 68)
            };
            pnlConfig.Controls.Add(lblOrigin);

            rbSourceGithub = new RadioButton
            {
                Text = "Descargar / Actualizar siempre desde GitHub oficial (https://github.com/Emmanuel270114/Avance-SAE.git)",
                Font = new Font("Segoe UI", 9f),
                ForeColor = ColorTexto,
                AutoSize = true,
                Checked = true,
                Location = new Point(18, 90)
            };
            pnlConfig.Controls.Add(rbSourceGithub);

            rbSourceLocal = new RadioButton
            {
                Text = "Copiar desde la carpeta local junto a este instalador (modo sin clonar de GitHub)",
                Font = new Font("Segoe UI", 9f),
                ForeColor = ColorSubtexto,
                AutoSize = true,
                Location = new Point(18, 113)
            };
            pnlConfig.Controls.Add(rbSourceLocal);

            chkDesktopBat = new CheckBox
            {
                Text = "Generar el script 'Iniciar_SiCAE.bat' en el Escritorio y en la carpeta del proyecto (configurado con tu ruta exacta y puerto 50000)",
                Font = new Font("Segoe UI", 9f, FontStyle.Bold),
                ForeColor = ColorGuindaOscuro,
                AutoSize = true,
                Checked = true,
                Location = new Point(18, 138)
            };
            pnlConfig.Controls.Add(chkDesktopBat);

            pnl.Controls.Add(pnlConfig);

            // Casilla de aceptación de dependencias (Requisito #3)
            chkAcceptDeps = new CheckBox
            {
                Text = "He leído qué dependencias se instalarán y para qué las ocupa SiCAE, y estoy de acuerdo en iniciar la instalación.",
                Font = new Font("Segoe UI", 9.75f, FontStyle.Bold),
                ForeColor = ColorGuinda,
                AutoSize = true,
                Location = new Point(10, 438),
                Cursor = Cursors.Hand
            };
            chkAcceptDeps.CheckedChanged += (s, e) =>
            {
                if (currentStep == 2)
                {
                    SetNextButtonEnabled(chkAcceptDeps.Checked);
                }
            };
            pnl.Controls.Add(chkAcceptDeps);

            stepPanels[2] = pnl;
        }

        private void SetNextButtonEnabled(bool enabled)
        {
            btnNext.Enabled = enabled;
            btnNext.BackColor = enabled ? ColorGuinda : Color.FromArgb(205, 210, 218);
            btnNext.ForeColor = enabled ? Color.White : Color.FromArgb(120, 125, 132);
        }

        // =========================================================================
        // PASO 4: PROGRESO DE INSTALACIÓN EN TIEMPO REAL
        // =========================================================================
        private void BuildStep3_InstallationProgress()
        {
            Panel pnl = new Panel { BackColor = ColorFondo };

            Label lblTitle = new Label
            {
                Text = "4. Instalando y Configurando SiCAE",
                Font = new Font("Segoe UI", 14f, FontStyle.Bold),
                ForeColor = ColorGuinda,
                AutoSize = true,
                Location = new Point(4, 2)
            };
            pnl.Controls.Add(lblTitle);

            lblProgressStatus = new Label
            {
                Text = "Preparando instalación...",
                Font = new Font("Segoe UI", 10f, FontStyle.Bold),
                ForeColor = ColorTexto,
                AutoSize = true,
                Location = new Point(6, 34)
            };
            pnl.Controls.Add(lblProgressStatus);

            progressBar = new ProgressBar
            {
                Location = new Point(6, 60),
                Size = new Size(812, 24),
                Minimum = 0,
                Maximum = 100,
                Value = 0,
                Style = ProgressBarStyle.Continuous
            };
            pnl.Controls.Add(progressBar);

            rtbLog = new RichTextBox
            {
                Location = new Point(6, 94),
                Size = new Size(812, 315),
                ReadOnly = true,
                BackColor = Color.FromArgb(24, 26, 31),
                ForeColor = Color.FromArgb(230, 235, 242),
                Font = new Font("Consolas", 9.2f),
                BorderStyle = BorderStyle.FixedSingle,
                ScrollBars = RichTextBoxScrollBars.Vertical
            };
            pnl.Controls.Add(rtbLog);

            pnlFinishActions = CreateCardPanel(new Point(6, 416), new Size(812, 54), Color.FromArgb(232, 247, 238), Color.FromArgb(140, 205, 165));
            pnlFinishActions.Visible = false;

            Label lblDoneMsg = new Label
            {
                Text = "🎉 ¡SiCAE quedó listo! Puedes iniciarlo con 'Iniciar_SiCAE.bat' desde tu Escritorio:",
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
                ForeColor = Color.FromArgb(20, 108, 67),
                AutoSize = true,
                Location = new Point(14, 16)
            };
            pnlFinishActions.Controls.Add(lblDoneMsg);

            btnLaunchNow = new Button
            {
                Text = "🚀 Iniciar Servidor SiCAE",
                Size = new Size(175, 34),
                Location = new Point(468, 9),
                FlatStyle = FlatStyle.Flat,
                BackColor = ColorExito,
                ForeColor = Color.White,
                Font = new Font("Segoe UI", 9f, FontStyle.Bold),
                Cursor = Cursors.Hand
            };
            btnLaunchNow.FlatAppearance.BorderSize = 0;
            btnLaunchNow.Click += (s, e) =>
            {
                string batPath = Path.Combine(txtInstallDir.Text.Trim(), "Iniciar_SiCAE.bat");
                if (File.Exists(batPath))
                {
                    Process.Start(new ProcessStartInfo(batPath) { UseShellExecute = true, WorkingDirectory = txtInstallDir.Text.Trim() });
                }
            };
            pnlFinishActions.Controls.Add(btnLaunchNow);

            btnOpenFolder = new Button
            {
                Text = "📁 Abrir Carpeta",
                Size = new Size(140, 34),
                Location = new Point(654, 9),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.White,
                ForeColor = ColorTexto,
                Font = new Font("Segoe UI", 9f, FontStyle.Bold),
                Cursor = Cursors.Hand
            };
            btnOpenFolder.Click += (s, e) =>
            {
                string dir = txtInstallDir.Text.Trim();
                if (Directory.Exists(dir))
                {
                    Process.Start("explorer.exe", dir);
                }
            };
            pnlFinishActions.Controls.Add(btnOpenFolder);

            pnl.Controls.Add(pnlFinishActions);

            stepPanels[3] = pnl;
        }

        // =========================================================================
        // NAVEGACIÓN ENTRE PASOS
        // =========================================================================
        private void ShowStep(int step)
        {
            currentStep = step;
            for (int i = 0; i < stepPanels.Length; i++)
            {
                stepPanels[i].Visible = (i == step);
            }

            lblStepIndicator.Text = string.Format("Paso {0} de 4", step + 1);
            btnBack.Enabled = (step > 0 && !isInstalling && !installSuccess);

            if (step == 0)
            {
                btnNext.Text = "Siguiente →";
                SetNextButtonEnabled(true);
                UpdateOSSelectionUI();
            }
            else if (step == 1)
            {
                btnNext.Text = "Siguiente →";
                SetNextButtonEnabled(true);
                RunPrerequisitesCheck();
            }
            else if (step == 2)
            {
                UpdateOSSelectionUI();
                btnNext.Text = "⚙️ Instalar Ahora";
                SetNextButtonEnabled(chkAcceptDeps != null && chkAcceptDeps.Checked);
            }
            else if (step == 3)
            {
                SetNextButtonEnabled(false);
            }
        }

        private void BtnBack_Click(object sender, EventArgs e)
        {
            if (currentStep > 0 && !isInstalling)
            {
                ShowStep(currentStep - 1);
            }
        }

        private void BtnNext_Click(object sender, EventArgs e)
        {
            if (currentStep == 0)
            {
                if (!rbWin11.Checked && !rbWin10.Checked)
                {
                    MessageBox.Show("Por favor selecciona el Sistema Operativo (Windows 10 o Windows 11).", "Selección requerida", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
                ShowStep(1);
            }
            else if (currentStep == 1)
            {
                RunPrerequisitesCheck();
                if (string.IsNullOrEmpty(detectedPythonExe) || !pythonVersionCompatible)
                {
                    DialogResult dr = MessageBox.Show(
                        "No se detectó una versión compatible de Python (se requiere específicamente Python 3.9, 3.10 o 3.11 de 64 bits).\r\n\r\n" +
                        "¿Deseas abrir ahora la Guía Paso a Paso para descargar e instalar Python 3.10.11 automáticamente?",
                        "Python 3.9 / 3.10 / 3.11 requerido",
                        MessageBoxButtons.YesNoCancel,
                        MessageBoxIcon.Warning);
                    if (dr == DialogResult.Yes)
                    {
                        OpenPrereqGuide("PYTHON");
                        return;
                    }
                    if (dr == DialogResult.Cancel) return;
                }
                ShowStep(2);
            }
            else if (currentStep == 2)
            {
                if (!chkAcceptDeps.Checked)
                {
                    MessageBox.Show(
                        "Antes de instalar, por favor marca la casilla confirmando que leíste qué dependencias se instalarán y para qué las ocupa SiCAE.",
                        "Confirmación de dependencias requerida",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Information);
                    return;
                }
                if (string.IsNullOrWhiteSpace(txtInstallDir.Text))
                {
                    MessageBox.Show("Por favor especifica una carpeta válida para instalar SiCAE.", "Ruta requerida", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }

                ShowStep(3);
                StartInstallationThread();
            }
            else if (currentStep == 3 && installSuccess)
            {
                Application.Exit();
            }
        }

        // =========================================================================
        // PROCESO COMPLETO DE INSTALACIÓN (HILO EN SEGUNDO PLANO)
        // =========================================================================
        private void StartInstallationThread()
        {
            isInstalling = true;
            installSuccess = false;
            btnBack.Enabled = false;
            btnNext.Enabled = false;
            rtbLog.Clear();

            bool isWin11 = rbWin11.Checked;
            string reqFileName = isWin11 ? "requirements.txt" : "requirements_w10.txt";
            string osLabel = isWin11 ? "Windows 11" : "Windows 10";
            string targetDir = txtInstallDir.Text.Trim();
            bool useGithub = rbSourceGithub.Checked;
            bool createDesktopBat = chkDesktopBat.Checked;

            Thread worker = new Thread(() =>
            {
                try
                {
                    AppendLog("======================================================================");
                    AppendLog("  INICIANDO INSTALACIÓN DE SiCAE (" + osLabel + ")");
                    AppendLog("  Carpeta destino : " + targetDir);
                    AppendLog("  Requerimientos  : " + reqFileName);
                    AppendLog("======================================================================\r\n");

                    // PASO 1: Obtener el código fuente (GitHub o Copia Local)
                    UpdateProgress(10, "Paso 1/6: Obteniendo código del proyecto SiCAE...");
                    ObtainProjectSource(targetDir, useGithub);

                    // PASO 2: Asegurar y normalizar requirements.txt y requirements_w10.txt en UTF-8
                    UpdateProgress(28, "Paso 2/6: Verificando y normalizando archivo " + reqFileName + " (UTF-8)...");
                    EnsureRequirementsUtf8(targetDir, isWin11, reqFileName);

                    // PASO 3: Copiar archivo .env automáticamente
                    UpdateProgress(35, "Paso 3/6: Configurando archivo de variables de entorno (.env)...");
                    ConfigureDotEnvFile(targetDir);

                    // PASO 4: Configurar PATH de GTK3 automáticamente si existe
                    UpdateProgress(42, "Paso 4/6: Verificando ruta de GTK3 Runtime en el PATH de Windows...");
                    EnsureDirectoryInUserPath(Directory.Exists(gtkBinFoundPath) ? gtkBinFoundPath : GTK3_DEFAULT_BIN);
                    AppendLog("✔ Ruta GTK3 (" + GTK3_DEFAULT_BIN + ") registrada en PATH de usuario.\r\n");

                    // PASO 5: Crear entorno virtual venv e instalar dependencias según el SO
                    UpdateProgress(50, "Paso 5/6: Creando entorno virtual 'venv' con Python...");
                    string pyExe = !string.IsNullOrEmpty(detectedPythonExe) ? detectedPythonExe : FindPythonExecutable(out detectedPythonVersion);
                    if (string.IsNullOrEmpty(pyExe))
                    {
                        throw new Exception("No se encontró Python instalado en el sistema. Instala Python 3.9+ y vuelve a intentarlo.");
                    }

                    string venvDir = Path.Combine(targetDir, "venv");
                    string venvPython = Path.Combine(venvDir, "Scripts", "python.exe");

                    if (!File.Exists(venvPython))
                    {
                        AppendLog("-> Ejecutando: \"" + pyExe + "\" -m venv venv");
                        int exitVenv = RunCommandLive(pyExe, "-m venv \"" + venvDir + "\"", targetDir);
                        if (exitVenv != 0 || !File.Exists(venvPython))
                        {
                            throw new Exception("Error al crear el entorno virtual 'venv' (Código " + exitVenv + ").");
                        }
                        AppendLog("✔ Entorno virtual 'venv' creado correctamente.\r\n");
                    }
                    else
                    {
                        AppendLog("✔ El entorno virtual 'venv' ya existe en la carpeta destino. Se reutilizará.\r\n");
                    }

                    UpdateProgress(62, "Paso 5/6: Actualizando pip e instalando " + reqFileName + " para " + osLabel + "...");
                    AppendLog("-> Actualizando pip, setuptools y wheel...");
                    RunCommandLive(venvPython, "-m pip install --upgrade pip setuptools wheel", targetDir);

                    string reqFullPath = Path.Combine(targetDir, reqFileName);
                    AppendLog("\r\n-> Instalando dependencias de " + osLabel + " (" + reqFileName + ")...");
                    AppendLog("   Comando: \"" + venvPython + "\" -m pip install -r \"" + reqFullPath + "\"\r\n");
                    int exitPip = RunCommandLive(venvPython, "-m pip install -r \"" + reqFullPath + "\"", targetDir);
                    if (exitPip != 0)
                    {
                        throw new Exception("Hubo un error al instalar algunos paquetes de " + reqFileName + " (Código " + exitPip + "). Revisa la bitácora superior.");
                    }
                    AppendLog("\r\n✔ Todas las dependencias de " + reqFileName + " se instalaron con éxito.\r\n");

                    // PASO 6: Generar scripts Iniciar_SiCAE.bat y Actualizar_SiCAE.bat con la ruta exacta
                    UpdateProgress(92, "Paso 6/6: Generando scripts Iniciar_SiCAE.bat y Actualizar_SiCAE.bat...");
                    GenerateBatchScripts(targetDir, reqFileName, createDesktopBat);

                    UpdateProgress(100, "✅ ¡Instalación de SiCAE completada exitosamente!");
                    AppendLog("======================================================================");
                    AppendLog("  🎉 ¡INSTALACIÓN FINALIZADA CON ÉXITO!");
                    AppendLog("  • Proyecto instalado en : " + targetDir);
                    AppendLog("  • Script de inicio      : " + Path.Combine(targetDir, "Iniciar_SiCAE.bat"));
                    if (createDesktopBat)
                    {
                        AppendLog("  • Copia en Escritorio   : " + Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Iniciar_SiCAE.bat"));
                    }
                    AppendLog("  • Servidor configurado  : http://localhost:50000");
                    AppendLog("======================================================================");

                    this.Invoke((MethodInvoker)delegate
                    {
                        isInstalling = false;
                        installSuccess = true;
                        pnlFinishActions.Visible = true;
                        btnNext.Text = "Finalizar y Salir";
                        SetNextButtonEnabled(true);
                        btnCancel.Visible = false;
                    });
                }
                catch (Exception ex)
                {
                    AppendLog("\r\n❌ ERROR DURANTE LA INSTALACIÓN:\r\n" + ex.Message);
                    this.Invoke((MethodInvoker)delegate
                    {
                        isInstalling = false;
                        lblProgressStatus.Text = "⚠️ Ocurrió un problema durante la instalación. Revisa los detalles abajo.";
                        lblProgressStatus.ForeColor = ColorError;
                        btnBack.Enabled = true;
                    });
                }
            });
            worker.IsBackground = true;
            worker.Start();
        }

        private void ObtainProjectSource(string targetDir, bool useGithub)
        {
            string installerDir = AppDomain.CurrentDomain.BaseDirectory;
            string parentProjectDir = Path.GetFullPath(Path.Combine(installerDir, ".."));
            bool localProjectAvailable = Directory.Exists(Path.Combine(parentProjectDir, "backend")) &&
                                         Directory.Exists(Path.Combine(parentProjectDir, "frontend"));

            if (!Directory.Exists(targetDir))
            {
                Directory.CreateDirectory(targetDir);
            }

            if (useGithub)
            {
                string gitExe = !string.IsNullOrEmpty(detectedGitExe) ? detectedGitExe : FindGitExecutable();
                if (!string.IsNullOrEmpty(gitExe))
                {
                    if (Directory.Exists(Path.Combine(targetDir, ".git")))
                    {
                        AppendLog("-> Repositorio Git detectado en la carpeta destino. Descargando actualizaciones (git pull)...");
                        int code = RunCommandLive(gitExe, "pull", targetDir);
                        if (code == 0)
                        {
                            AppendLog("✔ Proyecto actualizado desde GitHub (" + GITHUB_REPO_URL + ").\r\n");
                            return;
                        }
                    }
                    else if (Directory.GetFiles(targetDir).Length == 0 && Directory.GetDirectories(targetDir).Length == 0)
                    {
                        AppendLog("-> Clonando proyecto desde GitHub: " + GITHUB_REPO_URL);
                        int code = RunCommandLive(gitExe, "clone \"" + GITHUB_REPO_URL + "\" \"" + targetDir + "\"", installerDir);
                        if (code == 0 && Directory.Exists(Path.Combine(targetDir, "backend")))
                        {
                            AppendLog("✔ Repositorio clonado exitosamente desde GitHub.\r\n");
                            return;
                        }
                    }
                    else if (!Directory.Exists(Path.Combine(targetDir, "backend")))
                    {
                        string tempClone = Path.Combine(Path.GetTempPath(), "SiCAE_Clone_" + Guid.NewGuid().ToString("N").Substring(0, 6));
                        AppendLog("-> Clonando desde GitHub en carpeta temporal y copiando a destino...");
                        int code = RunCommandLive(gitExe, "clone \"" + GITHUB_REPO_URL + "\" \"" + tempClone + "\"", installerDir);
                        if (code == 0 && Directory.Exists(Path.Combine(tempClone, "backend")))
                        {
                            CopyDirectoryFiltered(tempClone, targetDir);
                            try { Directory.Delete(tempClone, true); } catch { }
                            AppendLog("✔ Archivos descargados desde GitHub y colocados en " + targetDir + ".\r\n");
                            return;
                        }
                    }
                    else
                    {
                        AppendLog("✔ La carpeta destino ya contiene los archivos del proyecto SiCAE.\r\n");
                        return;
                    }
                }

                // Fallback si no hay Git instalado: Descargar ZIP de GitHub
                if (!Directory.Exists(Path.Combine(targetDir, "backend")))
                {
                    AppendLog("-> Intentando descargar paquete ZIP directamente desde GitHub...");
                    if (TryDownloadGithubZip(targetDir))
                    {
                        AppendLog("✔ Proyecto descargado y extraído desde GitHub (ZIP).\r\n");
                        return;
                    }
                }
            }

            // Copia local si eligió modo local o si falló conexión a GitHub
            if (Directory.Exists(Path.Combine(targetDir, "backend")))
            {
                AppendLog("✔ Los archivos del proyecto ya están presentes en: " + targetDir + "\r\n");
                return;
            }

            if (localProjectAvailable)
            {
                AppendLog("-> Copiando archivos del proyecto desde la carpeta local: " + parentProjectDir);
                CopyDirectoryFiltered(parentProjectDir, targetDir);
                AppendLog("✔ Proyecto copiado correctamente a: " + targetDir + "\r\n");
            }
            else
            {
                throw new Exception("No se pudo obtener el código desde GitHub y no se encontró una copia local junto al instalador.");
            }
        }

        private bool TryDownloadGithubZip(string targetDir)
        {
            string tempZip = Path.Combine(Path.GetTempPath(), "sicae_github.zip");
            string tempExtract = Path.Combine(Path.GetTempPath(), "sicae_extract_" + Guid.NewGuid().ToString("N").Substring(0, 6));
            try
            {
                using (WebClient wc = new WebClient())
                {
                    wc.Headers.Add("User-Agent", "SiCAE-Installer");
                    try
                    {
                        wc.DownloadFile(GITHUB_ZIP_MAIN, tempZip);
                    }
                    catch
                    {
                        wc.DownloadFile(GITHUB_ZIP_MASTER, tempZip);
                    }
                }

                ZipFile.ExtractToDirectory(tempZip, tempExtract);
                string[] subDirs = Directory.GetDirectories(tempExtract);
                string sourceRoot = (subDirs.Length > 0) ? subDirs[0] : tempExtract;
                CopyDirectoryFiltered(sourceRoot, targetDir);
                return Directory.Exists(Path.Combine(targetDir, "backend"));
            }
            catch (Exception ex)
            {
                AppendLog("   (Aviso descarga ZIP: " + ex.Message + ")");
                return false;
            }
            finally
            {
                try { if (File.Exists(tempZip)) File.Delete(tempZip); } catch { }
                try { if (Directory.Exists(tempExtract)) Directory.Delete(tempExtract, true); } catch { }
            }
        }

        private void EnsureRequirementsUtf8(string targetDir, bool isWin11, string chosenReqFile)
        {
            string installerDir = AppDomain.CurrentDomain.BaseDirectory;
            string parentDir = Path.GetFullPath(Path.Combine(installerDir, ".."));

            // Asegurar tanto requirements.txt como requirements_w10.txt en la carpeta destino
            EnsureSingleReqFile(targetDir, installerDir, parentDir, "requirements.txt", EMBEDDED_REQ_W11);
            EnsureSingleReqFile(targetDir, installerDir, parentDir, "requirements_w10.txt", EMBEDDED_REQ_W10);

            AppendLog("✔ Archivo '" + chosenReqFile + "' verificado y normalizado en codificación UTF-8.\r\n");
        }

        private void EnsureSingleReqFile(string targetDir, string installerDir, string parentDir, string fileName, string fallbackContent)
        {
            string destFile = Path.Combine(targetDir, fileName);
            string instFile = Path.Combine(installerDir, fileName);
            string parentFile = Path.Combine(parentDir, fileName);

            string rawContent = null;
            if (File.Exists(destFile))
            {
                rawContent = ReadFileAutoEncoding(destFile);
            }
            else if (File.Exists(instFile))
            {
                rawContent = ReadFileAutoEncoding(instFile);
            }
            else if (File.Exists(parentFile))
            {
                rawContent = ReadFileAutoEncoding(parentFile);
            }

            if (string.IsNullOrWhiteSpace(rawContent))
            {
                rawContent = fallbackContent;
            }

            // Guardar en UTF-8 sin BOM para máxima compatibilidad con pip
            File.WriteAllText(destFile, rawContent.Trim() + "\r\n", new UTF8Encoding(false));
        }

        private string ReadFileAutoEncoding(string path)
        {
            byte[] bytes = File.ReadAllBytes(path);
            if (bytes.Length >= 2 && bytes[0] == 0xFF && bytes[1] == 0xFE)
            {
                return Encoding.Unicode.GetString(bytes, 2, bytes.Length - 2);
            }
            if (bytes.Length >= 2 && bytes[0] == 0xFE && bytes[1] == 0xFF)
            {
                return Encoding.BigEndianUnicode.GetString(bytes, 2, bytes.Length - 2);
            }
            if (bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF)
            {
                return Encoding.UTF8.GetString(bytes, 3, bytes.Length - 3);
            }
            // Detectar nulos intercalados típicos de UTF-16 sin BOM
            int nullCount = 0;
            int checkLen = Math.Min(bytes.Length, 100);
            for (int i = 0; i < checkLen; i++)
            {
                if (bytes[i] == 0) nullCount++;
            }
            if (checkLen > 10 && nullCount > checkLen / 3)
            {
                return Encoding.Unicode.GetString(bytes);
            }
            return Encoding.UTF8.GetString(bytes);
        }

        private void ConfigureDotEnvFile(string targetDir)
        {
            string installerDir = AppDomain.CurrentDomain.BaseDirectory;
            string parentDir = Path.GetFullPath(Path.Combine(installerDir, ".."));

            string destEnv = Path.Combine(targetDir, ".env");
            string destEnvExample = Path.Combine(targetDir, ".env.example");

            string envTemplate =
                "# Configuración de Base de Datos SQL Server\r\n" +
                "DB_USER=sa\r\n" +
                "DB_PASSWORD=tu_contraseña_sql\r\n" +
                "DB_HOST=148.204.107.22\r\n" +
                "DB_PORT=1433\r\n" +
                "DB_NAME=Base_pruebas\r\n" +
                "DB_DRIVER=ODBC Driver 17 for SQL Server\r\n\r\n" +
                "# Configuración de Correo Institucional Microsoft Graph (Exchange Online)\r\n" +
                "MICROSOFT_CLIENT_ID=\r\n" +
                "MICROSOFT_TENANT_ID=\r\n" +
                "MICROSOFT_CLIENT_SECRET=\r\n" +
                "SMTP_FROM=sicae@ipn.mx\r\n" +
                "SMTP_SUBJECT_PREFIX=SiCAE\r\n";

            if (!File.Exists(destEnvExample))
            {
                File.WriteAllText(destEnvExample, envTemplate, new UTF8Encoding(false));
            }

            if (File.Exists(destEnv))
            {
                AppendLog("✔ El archivo .env ya existe en la carpeta destino (se conservó intacto).\r\n");
                return;
            }

            // Buscar .env junto al instalador o en la carpeta raíz del proyecto
            string instEnv = Path.Combine(installerDir, ".env");
            string parentEnv = Path.Combine(parentDir, ".env");

            if (File.Exists(instEnv))
            {
                File.Copy(instEnv, destEnv, true);
                AppendLog("✔ Se copió automáticamente el archivo .env incluido con el instalador.\r\n");
            }
            else if (File.Exists(parentEnv))
            {
                File.Copy(parentEnv, destEnv, true);
                AppendLog("✔ Se copió automáticamente el archivo .env desde la carpeta raíz.\r\n");
            }
            else
            {
                File.WriteAllText(destEnv, envTemplate, new UTF8Encoding(false));
                AppendLog("✔ Se creó el archivo .env base a partir de la plantilla .env.example.\r\n");
            }
        }

        private void GenerateBatchScripts(string targetDir, string reqFileName, bool copyToDesktop)
        {
            // Script exacto solicitado por el usuario con la ruta dinámica donde se instaló el proyecto
            string batStartContent = string.Join("\r\n", new string[] {
                "@echo off",
                "",
                ":: === CONFIGURACIÓN ===",
                "set \"RUTA_PROYECTO=" + targetDir + "\"",
                "",
                ":: === IR A LA CARPETA DEL PROYECTO ===",
                "echo.",
                "echo ======================================",
                "echo  Posicionandose en la carpeta del proyecto...",
                "echo ======================================",
                "cd /d \"%RUTA_PROYECTO%\"",
                "if errorlevel 1 (",
                "\techo Error: No se pudo acceder a la carpeta %RUTA_PROYECTO%.",
                "\tpause",
                "\texit /b",
                ")",
                "echo Carpeta actual: %cd%",
                "",
                ":: === ASEGURAR LIBRERÍAS DE GTK3 EN EL PATH PARA WEASYPRINT ===",
                "if exist \"C:\\Program Files\\GTK3-Runtime Win64\\bin\" (",
                "\tset \"PATH=C:\\Program Files\\GTK3-Runtime Win64\\bin;%PATH%\"",
                ")",
                "",
                ":: === EJECUTAR UVICORN Y PASAR EL CONTROL AL CMD ===",
                "echo.",
                "echo Iniciando servidor SiCAE en http://localhost:50000 ...",
                "\"venv\\Scripts\\python.exe\" -m uvicorn backend.main:app --host 0.0.0.0 --port 50000",
                "",
                ":: Si uvicorn falla o se cierra, el archivo .bat no se cerrará gracias a lo siguiente:",
                "echo.",
                "echo ====================================================",
                "echo El servidor se detuvo o se cerro inesperadamente.",
                "echo ====================================================",
                "pause",
                "cmd /k"
            }) + "\r\n";

            string projectBatPath = Path.Combine(targetDir, "Iniciar_SiCAE.bat");
            File.WriteAllText(projectBatPath, batStartContent, Encoding.Default);
            AppendLog("✔ Script creado en el proyecto: " + projectBatPath);

            if (copyToDesktop)
            {
                try
                {
                    string desktopDir = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                    string desktopBatPath = Path.Combine(desktopDir, "Iniciar_SiCAE.bat");
                    File.WriteAllText(desktopBatPath, batStartContent, Encoding.Default);
                    AppendLog("✔ Script copiado al Escritorio: " + desktopBatPath);
                }
                catch (Exception ex)
                {
                    AppendLog("   (Aviso al copiar .bat al Escritorio: " + ex.Message + ")");
                }
            }

            // Script adicional para bajar actualizaciones de GitHub (git pull + pip install)
            string batUpdateContent = string.Join("\r\n", new string[] {
                "@echo off",
                ":: === ACTUALIZADOR AUTOMÁTICO DE SiCAE DESDE GITHUB ===",
                "set \"RUTA_PROYECTO=" + targetDir + "\"",
                "cd /d \"%RUTA_PROYECTO%\"",
                "echo ====================================================",
                "echo  Descargando actualizaciones desde GitHub (Avance-SAE)...",
                "echo ====================================================",
                "git pull origin main || git pull",
                "echo.",
                "echo ====================================================",
                "echo  Actualizando dependencias (" + reqFileName + ")...",
                "echo ====================================================",
                "\"venv\\Scripts\\python.exe\" -m pip install -r \"" + reqFileName + "\"",
                "echo.",
                "echo ¡Actualizacion finalizada!",
                "pause"
            }) + "\r\n";

            string updateBatPath = Path.Combine(targetDir, "Actualizar_SiCAE.bat");
            File.WriteAllText(updateBatPath, batUpdateContent, Encoding.Default);
            AppendLog("✔ Script de actualización creado: " + updateBatPath + "\r\n");
        }

        // =========================================================================
        // UTILIDADES DEL SISTEMA (DETECCIÓN DE PYTHON, GIT, ODBC, GTK3, PROCESOS)
        // =========================================================================
        private string FindPythonExecutable(out string versionText)
        {
            versionText = "";
            pythonVersionCompatible = false;
            incompatiblePythonFound = "";

            string localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string userProfile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            string progFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);

            // Priorizar ubicaciones específicas de Python 3.9, 3.10 y 3.11 (64 bits)
            List<string> candidates = new List<string>();
            string[] preferredFolders = new string[] { "Python310", "Python39", "Python311" };
            foreach (string pf in preferredFolders)
            {
                candidates.Add(Path.Combine(localApp, "Programs", "Python", pf, "python.exe"));
                candidates.Add(Path.Combine(progFiles, pf, "python.exe"));
                candidates.Add(Path.Combine(@"C:\", pf, "python.exe"));
            }

            candidates.Add(Path.Combine(userProfile, "miniconda3", "python.exe"));
            candidates.Add(Path.Combine(userProfile, "anaconda3", "python.exe"));
            candidates.Add("python");

            string pyPrograms = Path.Combine(localApp, "Programs", "Python");
            if (Directory.Exists(pyPrograms))
            {
                foreach (string dir in Directory.GetDirectories(pyPrograms, "Python3*"))
                {
                    string pExe = Path.Combine(dir, "python.exe");
                    if (!candidates.Contains(pExe)) candidates.Add(pExe);
                }
            }

            // También probar py launcher con flags de versión (-3.10, -3.9, -3.11)
            string[] pyLauncherVers = new string[] { "-3.10", "-3.9", "-3.11" };
            foreach (string vFlag in pyLauncherVers)
            {
                try
                {
                    ProcessStartInfo psiLauncher = new ProcessStartInfo
                    {
                        FileName = "py",
                        Arguments = vFlag + " -c \"import sys; print(sys.executable)\"",
                        RedirectStandardOutput = true,
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };
                    using (Process pL = Process.Start(psiLauncher))
                    {
                        string foundPath = pL.StandardOutput.ReadToEnd().Trim();
                        pL.WaitForExit(2500);
                        if (pL.ExitCode == 0 && !string.IsNullOrEmpty(foundPath) && File.Exists(foundPath))
                        {
                            candidates.Insert(0, foundPath);
                        }
                    }
                }
                catch { }
            }

            foreach (string cand in candidates)
            {
                try
                {
                    ProcessStartInfo psi = new ProcessStartInfo
                    {
                        FileName = cand,
                        Arguments = "-c \"import sys, struct; print(f'Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}|{sys.version_info.minor}|{struct.calcsize(\\\"P\\\")*8}|{sys.executable}')\"",
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };
                    using (Process p = Process.Start(psi))
                    {
                        string output = p.StandardOutput.ReadToEnd().Trim();
                        p.WaitForExit(3000);
                        if (p.ExitCode == 0 && output.StartsWith("Python 3", StringComparison.OrdinalIgnoreCase))
                        {
                            string[] parts = output.Split('|');
                            if (parts.Length >= 4)
                            {
                                string verStr = parts[0].Trim();
                                int minor = 0;
                                int bits = 64;
                                int.TryParse(parts[1].Trim(), out minor);
                                int.TryParse(parts[2].Trim(), out bits);
                                string realPath = parts[3].Trim();

                                // Compatible con SiCAE: Python 3.9, 3.10 o 3.11 de 64 bits
                                if ((minor == 9 || minor == 10 || minor == 11) && bits == 64)
                                {
                                    versionText = verStr + " (64-bit)";
                                    pythonVersionCompatible = true;
                                    return File.Exists(realPath) ? realPath : cand;
                                }
                                else if (string.IsNullOrEmpty(incompatiblePythonFound))
                                {
                                    incompatiblePythonFound = verStr + " (" + bits + "-bit)";
                                }
                            }
                        }
                    }
                }
                catch { }
            }
            return "";
        }

        private string FindGitExecutable()
        {
            string[] candidates = new string[]
            {
                "git",
                @"C:\Program Files\Git\cmd\git.exe",
                @"C:\Program Files\Git\bin\git.exe",
                @"C:\Program Files (x86)\Git\cmd\git.exe"
            };

            foreach (string cand in candidates)
            {
                try
                {
                    ProcessStartInfo psi = new ProcessStartInfo
                    {
                        FileName = cand,
                        Arguments = "--version",
                        RedirectStandardOutput = true,
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };
                    using (Process p = Process.Start(psi))
                    {
                        string outStr = p.StandardOutput.ReadToEnd().Trim();
                        p.WaitForExit(2500);
                        if (p.ExitCode == 0 && outStr.IndexOf("git version", StringComparison.OrdinalIgnoreCase) >= 0)
                        {
                            return cand;
                        }
                    }
                }
                catch { }
            }
            return "";
        }

        private bool CheckOdbcDriver17()
        {
            string[] regPaths = new string[]
            {
                @"SOFTWARE\ODBC\ODBCINST.INI\ODBC Driver 17 for SQL Server",
                @"SOFTWARE\WOW6432Node\ODBC\ODBCINST.INI\ODBC Driver 17 for SQL Server"
            };
            foreach (string rp in regPaths)
            {
                try
                {
                    using (RegistryKey key = Registry.LocalMachine.OpenSubKey(rp))
                    {
                        if (key != null) return true;
                    }
                }
                catch { }
            }
            return false;
        }

        private void CheckGtkStatus()
        {
            string[] possibleDirs = new string[]
            {
                @"C:\Program Files\GTK3-Runtime Win64\bin",
                @"C:\Program Files (x86)\GTK3-Runtime Win64\bin",
                @"C:\GTK3-Runtime Win64\bin"
            };

            gtkInstalled = false;
            foreach (string d in possibleDirs)
            {
                if (Directory.Exists(d) &&
                    (File.Exists(Path.Combine(d, "libgobject-2.0-0.dll")) || File.Exists(Path.Combine(d, "libcairo-2.dll")) || Directory.GetFiles(d, "*.dll").Length > 0))
                {
                    gtkInstalled = true;
                    gtkBinFoundPath = d;
                    break;
                }
            }

            string combinedPath = (Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.User) ?? "") + ";" +
                                  (Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.Machine) ?? "") + ";" +
                                  (Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.Process) ?? "");

            gtkInPath = combinedPath.IndexOf("GTK3-Runtime", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        private bool EnsureDirectoryInUserPath(string dirToAdd)
        {
            try
            {
                string userPath = Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.User) ?? "";
                if (userPath.IndexOf(dirToAdd, StringComparison.OrdinalIgnoreCase) < 0)
                {
                    string newPath = string.IsNullOrWhiteSpace(userPath) ? dirToAdd : (userPath.TrimEnd(';') + ";" + dirToAdd);
                    Environment.SetEnvironmentVariable("PATH", newPath, EnvironmentVariableTarget.User);
                }

                string procPath = Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.Process) ?? "";
                if (procPath.IndexOf(dirToAdd, StringComparison.OrdinalIgnoreCase) < 0)
                {
                    Environment.SetEnvironmentVariable("PATH", dirToAdd + ";" + procPath, EnvironmentVariableTarget.Process);
                }
                return true;
            }
            catch
            {
                return false;
            }
        }

        private void CopyDirectoryFiltered(string sourceDir, string targetDir)
        {
            HashSet<string> excludedDirs = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "venv", ".venv", "venvexit", "__pycache__", "Instalador_SiCAE", ".vs"
            };

            Directory.CreateDirectory(targetDir);

            foreach (string file in Directory.GetFiles(sourceDir))
            {
                string name = Path.GetFileName(file);
                if (name.Equals(".DS_Store", StringComparison.OrdinalIgnoreCase)) continue;
                string dest = Path.Combine(targetDir, name);
                File.Copy(file, dest, true);
            }

            foreach (string subDir in Directory.GetDirectories(sourceDir))
            {
                string dirName = Path.GetFileName(subDir);
                if (excludedDirs.Contains(dirName)) continue;
                CopyDirectoryFiltered(subDir, Path.Combine(targetDir, dirName));
            }
        }

        private int RunCommandLive(string fileName, string arguments, string workingDir)
        {
            ProcessStartInfo psi = new ProcessStartInfo
            {
                FileName = fileName,
                Arguments = arguments,
                WorkingDirectory = Directory.Exists(workingDir) ? workingDir : AppDomain.CurrentDomain.BaseDirectory,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8
            };

            using (Process proc = new Process { StartInfo = psi })
            {
                proc.OutputDataReceived += (s, e) => { if (e.Data != null) AppendLog("   " + e.Data); };
                proc.ErrorDataReceived += (s, e) => { if (e.Data != null) AppendLog("   " + e.Data); };

                proc.Start();
                proc.BeginOutputReadLine();
                proc.BeginErrorReadLine();
                proc.WaitForExit();
                return proc.ExitCode;
            }
        }

        private void AppendLog(string line)
        {
            if (rtbLog.InvokeRequired)
            {
                rtbLog.BeginInvoke((MethodInvoker)delegate { AppendLog(line); });
                return;
            }
            rtbLog.AppendText(line + "\r\n");
            rtbLog.SelectionStart = rtbLog.Text.Length;
            rtbLog.ScrollToCaret();
        }

        private void UpdateProgress(int val, string statusText)
        {
            if (this.InvokeRequired)
            {
                this.BeginInvoke((MethodInvoker)delegate { UpdateProgress(val, statusText); });
                return;
            }
            progressBar.Value = Math.Max(0, Math.Min(100, val));
            lblProgressStatus.Text = statusText;
        }

        private Panel CreateCardPanel(Point loc, Size size, Color bgColor, Color borderColor)
        {
            Panel p = new Panel
            {
                Location = loc,
                Size = size,
                BackColor = bgColor
            };
            p.Paint += (s, e) =>
            {
                bool isSelectedOsCard = (p == cardW11 && rbWin11 != null && rbWin11.Checked) ||
                                        (p == cardW10 && rbWin10 != null && rbWin10.Checked);
                if (isSelectedOsCard)
                {
                    using (Pen pen = new Pen(ColorGuinda, 2))
                    {
                        e.Graphics.DrawRectangle(pen, 1, 1, p.Width - 2, p.Height - 2);
                    }
                }
                else
                {
                    using (Pen pen = new Pen(borderColor, 1))
                    {
                        e.Graphics.DrawRectangle(pen, 0, 0, p.Width - 1, p.Height - 1);
                    }
                }
            };
            return p;
        }

        private void OpenUrl(string url)
        {
            try
            {
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                MessageBox.Show("No se pudo abrir el navegador automáticamente. Visita:\r\n" + url + "\r\n(" + ex.Message + ")");
            }
        }
    }

    // =========================================================================
    // VENTANA EMERGENTE DE GUÍA PASO A PASO Y DESCARGA/INSTALACIÓN ASISTIDA
    // =========================================================================
    public class PrerequisiteGuideDialog : Form
    {
        private readonly Color ColorGuinda = Color.FromArgb(107, 29, 58);
        private readonly Color ColorDorado = Color.FromArgb(197, 155, 39);
        private readonly Color ColorExito = Color.FromArgb(25, 135, 84);
        private readonly Color ColorFondo = Color.FromArgb(246, 247, 249);
        private readonly Color ColorTexto = Color.FromArgb(33, 37, 41);

        private string reqType;
        private string downloadUrl;
        private string secondaryUrl;
        private string fileNameToSave;
        private string silentArgs;
        private bool isDownloading = false;

        private ProgressBar pbDownload;
        private Label lblDlStatus;
        private Button btnDownloadAndRunWizard;
        private Button btnDownloadSilent;
        private Button btnOpenBrowser;

        public PrerequisiteGuideDialog(string type, Icon appIcon)
        {
            this.reqType = type;
            if (appIcon != null) this.Icon = appIcon;
            InitializeGuideUI();
        }

        private void InitializeGuideUI()
        {
            this.Size = new Size(720, 560);
            this.StartPosition = FormStartPosition.CenterParent;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.BackColor = ColorFondo;
            this.Font = new Font("Segoe UI", 9.5f);

            string titleText = "";
            string versionBadge = "";
            string whyVersionText = "";
            string stepsText = "";
            string wizardBtnText = "";
            string silentBtnText = "";

            if (reqType == "PYTHON")
            {
                this.Text = "Guía Paso a Paso e Instalación — Python 3.10.11 / 3.9.13 (64 bits)";
                titleText = "1. Instalación de Python (Versión compatible con SiCAE)";
                versionBadge = "📌 Versión requerida: Python 3.9, 3.10 o 3.11 (64 bits)  |  Instalador incluido: Python 3.10.11 (64-bit)";
                whyVersionText =
                    "¿Por qué se necesita específicamente Python 3.9, 3.10 o 3.11?\r\n" +
                    "• Si descargas Python 3.12, 3.13 o 3.14 de la portada de python.org, fallará la instalación de 'pyodbc==4.0.35' y 'MarkupSafe==2.1.3' porque esas versiones no tienen binarios precompilados (.whl) para Python 3.12+.\r\n" +
                    "• Python 3.8 o inferior tampoco es compatible porque 'pycairo==1.28.0' y 'pydantic_core==2.46.4' exigen mínimo Python 3.9.";
                stepsText =
                    "GUÍA PASO A PASO PARA INSTALAR PYTHON 3.10.11 (64 BITS):\r\n\r\n" +
                    "OPCIÓN A — Instalación Automática en 1 Clic (Recomendada):\r\n" +
                    "  1. Haz clic en el botón verde \"⚡ Descargar e Instalar Automáticamente (con PATH)\" de abajo.\r\n" +
                    "  2. Espera a que la barra llegue al 100% y acepta el permiso de Windows si aparece.\r\n" +
                    "  3. El asistente instalará Python 3.10.11 de 64 bits y activará la variable PATH automáticamente.\r\n\r\n" +
                    "OPCIÓN B — Instalación Guiada con la Ventana de Python:\r\n" +
                    "  1. Haz clic en \"📥 Descargar y Abrir Asistente de Python 3.10.11\".\r\n" +
                    "  2. ¡MUY IMPORTANTE!: En la primera pantalla que se abre, marca la casilla de hasta abajo:\r\n" +
                    "     [✔] Add Python 3.10 to PATH\r\n" +
                    "  3. Haz clic arriba en \"Install Now\" y acepta el permiso de Administrador.\r\n" +
                    "  4. Cuando termine, si aparece \"Disable path length limit\", haz clic en esa opción y luego en \"Close\".";
                downloadUrl = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe";
                secondaryUrl = "https://www.python.org/downloads/release/python-31011/";
                fileNameToSave = "python-3.10.11-amd64.exe";
                silentArgs = "/passive InstallAllUsers=0 PrependPath=1 Include_test=0";
                wizardBtnText = "📥 Descargar y Abrir Asistente";
                silentBtnText = "⚡ Descargar e Instalar Automáticamente (con PATH)";
            }
            else if (reqType == "GIT")
            {
                this.Text = "Guía Paso a Paso e Instalación — Git para Windows (64 bits)";
                titleText = "2. Instalación de Git para Windows (64 bits)";
                versionBadge = "📌 Versión requerida: Git for Windows 2.x (64 bits)  |  Instalador directo: Git v2.47.1 (64-bit)";
                whyVersionText =
                    "¿Para qué lo ocupa SiCAE?\r\n" +
                    "• Permite clonar el proyecto directamente del repositorio oficial (https://github.com/Emmanuel270114/Avance-SAE.git) y usar el script 'Actualizar_SiCAE.bat' (git pull) cada vez que haya mejoras.";
                stepsText =
                    "GUÍA PASO A PASO PARA INSTALAR GIT:\r\n\r\n" +
                    "OPCIÓN A — Instalación Automática en 1 Clic (Recomendada):\r\n" +
                    "  1. Haz clic en el botón verde \"⚡ Descargar e Instalar Automáticamente\" de abajo.\r\n" +
                    "  2. Acepta el permiso de Administrador de Windows y espera unos segundos a que termine.\r\n\r\n" +
                    "OPCIÓN B — Instalación Guiada con la Ventana de Git:\r\n" +
                    "  1. Haz clic en \"📥 Descargar y Abrir Asistente de Git\".\r\n" +
                    "  2. Presiona \"Next >\" en las pantallas dejando las opciones recomendadas por defecto.\r\n" +
                    "  3. En la pantalla \"Adjusting your PATH environment\", verifica que esté marcada la opción del medio:\r\n" +
                    "     (•) Git from the command line and also from 3rd-party software\r\n" +
                    "  4. Continúa dando clic en \"Next >\" hasta \"Install\" y al terminar pulsa \"Finish\".";
                downloadUrl = "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe";
                secondaryUrl = "https://git-scm.com/download/win";
                fileNameToSave = "Git-2.47.1-64-bit.exe";
                silentArgs = "/VERYSILENT /NORESTART /NOCANCEL /SP-";
                wizardBtnText = "📥 Descargar y Abrir Asistente de Git";
                silentBtnText = "⚡ Descargar e Instalar Automáticamente";
            }
            else if (reqType == "ODBC17")
            {
                this.Text = "Guía Paso a Paso e Instalación — Microsoft ODBC Driver 17 for SQL Server";
                titleText = "3. Instalación de Microsoft ODBC Driver 17 for SQL Server";
                versionBadge = "📌 Versión exacta requerida: ODBC Driver 17 for SQL Server (x64) — v17.10.6";
                whyVersionText =
                    "¿Por qué tiene que ser específicamente la versión 17?\r\n" +
                    "• La cadena de conexión de SiCAE tiene configurado explícitamente 'DRIVER={ODBC Driver 17 for SQL Server}'. Si solo tienes el Driver 18 o ninguno, SQL Server rechazará la conexión con error IM002.";
                stepsText =
                    "GUÍA PASO A PASO PARA INSTALAR ODBC DRIVER 17:\r\n\r\n" +
                    "  1. Haz clic en el botón \"📥 Descargar y Ejecutar Instalador ODBC 17 (MSI)\" de abajo.\r\n" +
                    "  2. Se descargará el paquete oficial de Microsoft (4.6 MB) y se abrirá automáticamente.\r\n" +
                    "  3. En la ventana de bienvenida de Microsoft ODBC Driver 17, haz clic en \"Next\".\r\n" +
                    "  4. Selecciona \"I accept the terms in the license agreement\" y haz clic en \"Next\".\r\n" +
                    "  5. En selección de componentes deja \"Client Components\" y haz clic en \"Next\" → \"Install\".\r\n" +
                    "  6. Acepta el permiso de Administrador de Windows y al concluir haz clic en \"Finish\".";
                downloadUrl = "https://go.microsoft.com/fwlink/?linkid=2249004";
                secondaryUrl = "https://learn.microsoft.com/es-es/sql/connect/odbc/download-odbc-driver-for-sql-server";
                fileNameToSave = "msodbcsql_17_win64.msi";
                silentArgs = "";
                wizardBtnText = "📥 Descargar y Ejecutar Instalador ODBC 17 (MSI)";
                silentBtnText = "";
            }
            else // GTK3
            {
                this.Text = "Guía Paso a Paso e Instalación — GTK3 Runtime Win64 (Motor PDF WeasyPrint)";
                titleText = "4. Instalación de GTK3 Runtime Win64 (v3.24.31)";
                versionBadge = "📌 Versión requerida: GTK3-Runtime Win64 v3.24.31-2022-01-04 (64 bits)";
                whyVersionText =
                    "¿Por qué se requiere esta versión específica?\r\n" +
                    "• WeasyPrint 60.0 y PyCairo 1.28 requieren las librerías gráficas C de 64 bits (libgobject-2.0-0.dll, libcairo-2.dll, libpango-1.0-0.dll) en 'C:\\Program Files\\GTK3-Runtime Win64\\bin' para generar los Acuses y Oficios en PDF.";
                stepsText =
                    "GUÍA PASO A PASO PARA INSTALAR GTK3 RUNTIME WIN64:\r\n\r\n" +
                    "  1. Haz clic en el botón \"📥 Descargar y Ejecutar Instalador GTK3 Runtime\" de abajo.\r\n" +
                    "  2. Cuando se abra el instalador de GTK3, haz clic en \"Next >\" y luego en \"I Agree\".\r\n" +
                    "  3. En 'Choose Components', deja todo marcado por defecto (incluyendo \"Set up PATH environment variable\") y pulsa \"Next >\".\r\n" +
                    "  4. ¡IMPORTANTE!: En 'Choose Install Location', NO cambies la carpeta; deja la ruta por defecto:\r\n" +
                    "     C:\\Program Files\\GTK3-Runtime Win64\r\n" +
                    "  5. Haz clic en \"Install\", espera a que termine y haz clic en \"Finish\".\r\n" +
                    "  6. Al cerrar esta ventana, el instalador de SiCAE registrará automáticamente la carpeta en el PATH de Windows.";
                downloadUrl = "https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases/download/2022-01-04/gtk3-runtime-3.24.31-2022-01-04-ts-win64.exe";
                secondaryUrl = "https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases/tag/2022-01-04";
                fileNameToSave = "gtk3-runtime-3.24.31-win64.exe";
                silentArgs = "/S";
                wizardBtnText = "📥 Descargar y Abrir Instalador GTK3";
                silentBtnText = "⚡ Descargar e Instalar Silenciosamente (Ruta por defecto)";
            }

            // Encabezado
            Panel pnlTop = new Panel
            {
                Dock = DockStyle.Top,
                Height = 56,
                BackColor = ColorGuinda
            };
            Label lblHeader = new Label
            {
                Text = titleText,
                Font = new Font("Segoe UI", 12.5f, FontStyle.Bold),
                ForeColor = Color.White,
                AutoSize = true,
                Location = new Point(18, 15)
            };
            pnlTop.Controls.Add(lblHeader);
            Panel pnlGold = new Panel { Dock = DockStyle.Bottom, Height = 3, BackColor = ColorDorado };
            pnlTop.Controls.Add(pnlGold);
            this.Controls.Add(pnlTop);

            // Cuerpo
            Panel pnlBody = new Panel { Dock = DockStyle.Fill, Padding = new Padding(18) };

            Label lblBadge = new Label
            {
                Text = versionBadge,
                Font = new Font("Segoe UI", 9.2f, FontStyle.Bold),
                ForeColor = Color.FromArgb(135, 70, 0),
                BackColor = Color.FromArgb(255, 246, 225),
                BorderStyle = BorderStyle.FixedSingle,
                AutoSize = false,
                TextAlign = ContentAlignment.MiddleLeft,
                Padding = new Padding(8, 0, 0, 0),
                Size = new Size(668, 30),
                Location = new Point(18, 68)
            };
            this.Controls.Add(lblBadge);

            Label lblWhy = new Label
            {
                Text = whyVersionText,
                Font = new Font("Segoe UI", 8.8f),
                ForeColor = ColorTexto,
                BackColor = Color.White,
                BorderStyle = BorderStyle.FixedSingle,
                Padding = new Padding(10, 6, 10, 6),
                AutoSize = false,
                Size = new Size(668, 72),
                Location = new Point(18, 104)
            };
            this.Controls.Add(lblWhy);

            RichTextBox rtbSteps = new RichTextBox
            {
                Location = new Point(18, 184),
                Size = new Size(668, 210),
                ReadOnly = true,
                BackColor = Color.White,
                BorderStyle = BorderStyle.FixedSingle,
                Font = new Font("Segoe UI", 9.3f),
                Text = stepsText
            };
            this.Controls.Add(rtbSteps);

            lblDlStatus = new Label
            {
                Text = "Listo para descargar e instalar la versión oficial requerida.",
                Font = new Font("Segoe UI", 9f, FontStyle.Bold),
                ForeColor = ColorGuinda,
                AutoSize = false,
                Size = new Size(668, 20),
                Location = new Point(18, 402)
            };
            this.Controls.Add(lblDlStatus);

            pbDownload = new ProgressBar
            {
                Location = new Point(18, 425),
                Size = new Size(668, 18),
                Minimum = 0,
                Maximum = 100,
                Value = 0
            };
            this.Controls.Add(pbDownload);

            // Botones de acción
            int xPos = 18;
            if (!string.IsNullOrEmpty(silentBtnText))
            {
                btnDownloadSilent = new Button
                {
                    Text = silentBtnText,
                    Size = new Size(325, 36),
                    Location = new Point(xPos, 454),
                    FlatStyle = FlatStyle.Flat,
                    BackColor = ColorExito,
                    ForeColor = Color.White,
                    Font = new Font("Segoe UI", 8.8f, FontStyle.Bold),
                    Cursor = Cursors.Hand
                };
                btnDownloadSilent.FlatAppearance.BorderSize = 0;
                btnDownloadSilent.Click += (s, e) => StartDownloadAndExecute(true);
                this.Controls.Add(btnDownloadSilent);
                xPos += 335;
            }

            btnDownloadAndRunWizard = new Button
            {
                Text = wizardBtnText,
                Size = new Size(string.IsNullOrEmpty(silentBtnText) ? 360 : 215, 36),
                Location = new Point(xPos, 454),
                FlatStyle = FlatStyle.Flat,
                BackColor = ColorGuinda,
                ForeColor = Color.White,
                Font = new Font("Segoe UI", 8.8f, FontStyle.Bold),
                Cursor = Cursors.Hand
            };
            btnDownloadAndRunWizard.FlatAppearance.BorderSize = 0;
            btnDownloadAndRunWizard.Click += (s, e) => StartDownloadAndExecute(false);
            this.Controls.Add(btnDownloadAndRunWizard);

            btnOpenBrowser = new Button
            {
                Text = "🌐 Web Oficial",
                Size = new Size(105, 36),
                Location = new Point(581, 454),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.White,
                ForeColor = ColorTexto,
                Font = new Font("Segoe UI", 8.5f),
                Cursor = Cursors.Hand
            };
            btnOpenBrowser.Click += (s, e) =>
            {
                try { Process.Start(new ProcessStartInfo(secondaryUrl) { UseShellExecute = true }); } catch { }
            };
            this.Controls.Add(btnOpenBrowser);
        }

        private void StartDownloadAndExecute(bool runSilent)
        {
            if (isDownloading) return;
            isDownloading = true;
            if (btnDownloadSilent != null) btnDownloadSilent.Enabled = false;
            btnDownloadAndRunWizard.Enabled = false;

            string destPath = Path.Combine(Path.GetTempPath(), fileNameToSave);
            lblDlStatus.Text = "Descargando instalador oficial (" + fileNameToSave + ")... 0%";
            pbDownload.Value = 0;

            WebClient wc = new WebClient();
            wc.Headers.Add("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SiCAE-Installer");
            wc.DownloadProgressChanged += (s, e) =>
            {
                pbDownload.Value = Math.Max(0, Math.Min(100, e.ProgressPercentage));
                double mbReceived = e.BytesReceived / (1024.0 * 1024.0);
                double mbTotal = e.TotalBytesToReceive / (1024.0 * 1024.0);
                if (mbTotal > 0)
                {
                    lblDlStatus.Text = string.Format("Descargando {0}: {1:0.0} MB / {2:0.0} MB ({3}%)", fileNameToSave, mbReceived, mbTotal, e.ProgressPercentage);
                }
                else
                {
                    lblDlStatus.Text = string.Format("Descargando {0}: {1:0.0} MB...", fileNameToSave, mbReceived);
                }
            };

            wc.DownloadFileCompleted += (s, e) =>
            {
                isDownloading = false;
                if (e.Error != null)
                {
                    lblDlStatus.Text = "⚠️ Error al descargar automáticamente. Se abrirá el enlace directo en tu navegador.";
                    if (btnDownloadSilent != null) btnDownloadSilent.Enabled = true;
                    btnDownloadAndRunWizard.Enabled = true;
                    try { Process.Start(new ProcessStartInfo(downloadUrl) { UseShellExecute = true }); } catch { }
                    return;
                }

                pbDownload.Value = 100;
                lblDlStatus.Text = "✅ Descarga completa. Ejecutando instalador (esperando a que finalice)...";

                Thread execThread = new Thread(() =>
                {
                    try
                    {
                        ProcessStartInfo psi;
                        if (destPath.EndsWith(".msi", StringComparison.OrdinalIgnoreCase))
                        {
                            psi = new ProcessStartInfo("msiexec.exe", "/i \"" + destPath + "\"")
                            {
                                UseShellExecute = true
                            };
                        }
                        else
                        {
                            string args = (runSilent && !string.IsNullOrEmpty(silentArgs)) ? silentArgs : "";
                            psi = new ProcessStartInfo(destPath, args)
                            {
                                UseShellExecute = true
                            };
                        }

                        using (Process p = Process.Start(psi))
                        {
                            if (p != null) p.WaitForExit();
                        }

                        // Si se instaló GTK3, asegurar de inmediato su carpeta bin en el PATH del usuario y proceso
                        if (reqType == "GTK3" && Directory.Exists(@"C:\Program Files\GTK3-Runtime Win64\bin"))
                        {
                            string gtkBin = @"C:\Program Files\GTK3-Runtime Win64\bin";
                            string uPath = Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.User) ?? "";
                            if (uPath.IndexOf(gtkBin, StringComparison.OrdinalIgnoreCase) < 0)
                            {
                                Environment.SetEnvironmentVariable("PATH", uPath.TrimEnd(';') + ";" + gtkBin, EnvironmentVariableTarget.User);
                            }
                            string pPath = Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.Process) ?? "";
                            if (pPath.IndexOf(gtkBin, StringComparison.OrdinalIgnoreCase) < 0)
                            {
                                Environment.SetEnvironmentVariable("PATH", gtkBin + ";" + pPath, EnvironmentVariableTarget.Process);
                            }
                        }

                        this.Invoke((MethodInvoker)delegate
                        {
                            lblDlStatus.Text = "🎉 Proceso finalizado. Puedes cerrar esta ventana para actualizar la verificación.";
                            if (btnDownloadSilent != null) btnDownloadSilent.Enabled = true;
                            btnDownloadAndRunWizard.Enabled = true;
                        });
                    }
                    catch (Exception ex)
                    {
                        this.Invoke((MethodInvoker)delegate
                        {
                            lblDlStatus.Text = "⚠️ Aviso al ejecutar el instalador: " + ex.Message;
                            if (btnDownloadSilent != null) btnDownloadSilent.Enabled = true;
                            btnDownloadAndRunWizard.Enabled = true;
                        });
                    }
                });
                execThread.IsBackground = true;
                execThread.Start();
            };

            wc.DownloadFileAsync(new Uri(downloadUrl), destPath);
        }
    }
}

