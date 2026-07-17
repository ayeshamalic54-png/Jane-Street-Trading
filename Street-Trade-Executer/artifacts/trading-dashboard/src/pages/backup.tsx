import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { Database, Download, Upload, AlertTriangle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export default function Backup() {
  const { toast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [isRestoring, setIsRestoring] = useState(false);
  const isReadOnly = localStorage.getItem("wasee_role") === "user";

  const handleExport = () => {
    // Standard fetch/download for JSON backup file
    window.location.href = "/api/backup/export";
    toast({
      title: "📥 Backup Export Started",
      description: "Downloading your database backup file.",
    });
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleRestore = async () => {
    if (!file) {
      toast({
        title: "⚠️ No File Selected",
        description: "Please select a backup JSON file to restore.",
        variant: "destructive",
      });
      return;
    }

    if (isReadOnly) {
      toast({
        title: "🚫 Access Denied",
        description: "Read-only users are not allowed to perform database restores.",
        variant: "destructive",
      });
      return;
    }

    const confirmRestore = window.confirm(
      "WARNING: Restoring a backup will overwrite ALL current trades, signals, metrics, and bot configurations. This action CANNOT be undone. Are you sure you want to continue?"
    );

    if (!confirmRestore) return;

    setIsRestoring(true);
    try {
      const reader = new FileReader();
      reader.onload = async (event) => {
        try {
          const json = JSON.parse(event.target?.result as string);
          
          const res = await fetch("/api/backup/import", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(json),
          });

          const data = await res.json();
          if (res.ok) {
            toast({
              title: "✅ Restore Successful",
              description: data.message || "Database backup has been restored successfully.",
            });
            setFile(null);
          } else {
            toast({
              title: "❌ Restore Failed",
              description: data.error || "Failed to restore database from backup file.",
              variant: "destructive",
            });
          }
        } catch (e) {
          toast({
            title: "❌ Invalid File Format",
            description: "The selected file is not a valid JSON backup file.",
            variant: "destructive",
          });
        } finally {
          setIsRestoring(false);
        }
      };
      reader.readAsText(file);
    } catch (err) {
      toast({
        title: "❌ File Read Error",
        description: "An error occurred while reading the selected file.",
        variant: "destructive",
      });
      setIsRestoring(false);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-auto bg-background p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Database className="h-6 w-6 text-indigo-400" /> Database Backup &amp; Restore
        </h2>
        <p className="text-sm text-muted-foreground font-sans">
          Export full database snapshot or restore systems to historical checkpoints.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* EXPORT PANEL */}
        <Card className="bg-card/40 border-border/80 backdrop-blur-sm shadow-md transition-all hover:border-emerald-500/30">
          <CardHeader>
            <CardTitle className="text-sm font-semibold tracking-wide uppercase font-mono text-emerald-400 flex items-center gap-2">
              <Download className="h-4 w-4" /> Export Backup
            </CardTitle>
            <CardDescription className="font-sans text-xs">
              Download all bot configurations, trade histories, signals log, and performance metrics as a single JSON file.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-2">
            <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-sm p-4 text-xs font-mono text-emerald-400/90 leading-relaxed">
              📦 Backup payload version 1.0<br />
              💾 Compressed JSON format<br />
              🔒 Encryption standard compliant
            </div>
            <Button
              onClick={handleExport}
              className="w-full font-mono text-xs bg-emerald-600 text-white hover:bg-emerald-500 gap-2 h-10 font-bold"
            >
              <Download className="h-4 w-4" /> EXPORT JSON BACKUP
            </Button>
          </CardContent>
        </Card>

        {/* RESTORE PANEL */}
        <Card className="bg-card/40 border-border/80 backdrop-blur-sm shadow-md transition-all hover:border-rose-500/30">
          <CardHeader>
            <CardTitle className="text-sm font-semibold tracking-wide uppercase font-mono text-rose-400 flex items-center gap-2">
              <Upload className="h-4 w-4" /> Restore Backup
            </CardTitle>
            <CardDescription className="font-sans text-xs">
              Upload a previously downloaded JSON backup file to restore the system state.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-2">
            <Alert variant="destructive" className="bg-rose-500/5 text-rose-400 border-rose-500/10 py-3">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <AlertTitle className="font-mono text-xs font-bold uppercase tracking-wider">Crucial Warning</AlertTitle>
              <AlertDescription className="font-sans text-[11px] leading-relaxed">
                Restoring a backup overwrites the active configuration, open trades, and logs. Daily statistics will reset.
              </AlertDescription>
            </Alert>

            <div className="space-y-2">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block">
                Select Backup File (.json)
              </label>
              <Input
                type="file"
                accept=".json"
                onChange={handleFileChange}
                disabled={isReadOnly || isRestoring}
                className="font-mono text-xs border-border bg-zinc-950/40 text-muted-foreground file:bg-zinc-800 file:text-zinc-200 file:border-0 file:rounded-sm file:mr-4 file:px-3 file:py-1 file:cursor-pointer hover:file:bg-zinc-700"
              />
            </div>

            <Button
              onClick={handleRestore}
              disabled={isReadOnly || isRestoring || !file}
              className="w-full font-mono text-xs bg-rose-600 text-white hover:bg-rose-500 gap-2 h-10 font-bold"
            >
              <Upload className="h-4 w-4" /> {isRestoring ? "RESTORING..." : "RESTORE JSON BACKUP"}
            </Button>

            {isReadOnly && (
              <div className="text-[10px] text-rose-500 font-mono text-center animate-pulse">
                🚫 ACCESS DENIED: Viewers cannot restore databases.
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
