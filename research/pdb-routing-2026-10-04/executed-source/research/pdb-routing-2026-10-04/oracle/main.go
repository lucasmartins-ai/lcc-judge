// Independent conversion reference: call the pinned upstream Kubernetes library.
package main

import (
    "bufio"
    "encoding/json"
    "fmt"
    "os"
    "strconv"
    "strings"

    "k8s.io/apimachinery/pkg/util/intstr"
    "k8s.io/apimachinery/pkg/util/validation"
)

type Input struct { ID string `json:"id"`; Replicas int `json:"replicas"`; Value json.RawMessage `json:"value"` }
type Output struct { ID string `json:"id"`; Valid bool `json:"valid"`; Scaled int `json:"scaled"`; Error string `json:"error,omitempty"` }

func evaluate(in Input) Output {
    out := Output{ID:in.ID}
    var value intstr.IntOrString
    if err := json.Unmarshal(in.Value,&value);err!=nil {out.Error=err.Error();return out}
    if value.Type==intstr.String {
        if errors:=validation.IsValidPercent(value.StrVal);len(errors)>0 {out.Error=strings.Join(errors,"; ");return out}
        n,err:=strconv.Atoi(strings.TrimSuffix(value.StrVal,"%"))
        if err!=nil || n>100 {out.Error="percentage outside range";return out}
    } else if value.IntVal<0 {out.Error="negative count";return out}
    scaled,err:=intstr.GetScaledValueFromIntOrPercent(&value,in.Replicas,true)
    if err!=nil {out.Error=err.Error();return out}
    out.Valid=true;out.Scaled=scaled;return out
}

func main() {
    scanner:=bufio.NewScanner(os.Stdin)
    writer:=bufio.NewWriter(os.Stdout);defer writer.Flush()
    for scanner.Scan() {
        var in Input
        if err:=json.Unmarshal(scanner.Bytes(),&in);err!=nil {panic(err)}
        data,err:=json.Marshal(evaluate(in));if err!=nil {panic(err)}
        fmt.Fprintln(writer,string(data))
    }
    if err:=scanner.Err();err!=nil {panic(err)}
}
