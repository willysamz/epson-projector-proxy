{{- define "epson-projector-proxy.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- define "epson-projector-proxy.fullname" -}}
{{- if .Values.fullnameOverride }}{{ .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}{{- $name := default .Chart.Name .Values.nameOverride }}{{ printf "%s" $name | trunc 63 | trimSuffix "-" }}{{- end }}
{{- end }}
{{- define "epson-projector-proxy.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- define "epson-projector-proxy.labels" -}}
helm.sh/chart: {{ include "epson-projector-proxy.chart" . }}
{{ include "epson-projector-proxy.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
{{- define "epson-projector-proxy.selectorLabels" -}}
app.kubernetes.io/name: {{ include "epson-projector-proxy.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
