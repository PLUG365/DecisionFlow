import type { IOperationResult } from "@microsoft/power-apps/data";
import { getClient } from "@microsoft/power-apps/data";

import { dataSourcesInfo } from "../../.power/schemas/appschemas/dataSourcesInfo";

export type GenerateAiDecisionInput = {
  text: string;
};

export type GenerateAiDecisionOutput = {
  ok?: string;
  applicationid?: string;
  message?: string;
};

export class Application_GenerateAiDecisionService {
  private static readonly dataSourceName = "application_generateaidecision";

  private static readonly client = getClient(dataSourcesInfo);

  public static async Run(
    input: GenerateAiDecisionInput,
  ): Promise<IOperationResult<GenerateAiDecisionOutput>> {
    const params: { input: GenerateAiDecisionInput } = { input };
    const allParams = { ...params, "api-version": "2015-02-01-preview" };
    return Application_GenerateAiDecisionService.client.executeAsync<
      { input: GenerateAiDecisionInput },
      GenerateAiDecisionOutput
    >({
      connectorOperation: {
        tableName: Application_GenerateAiDecisionService.dataSourceName,
        operationName: "Run",
        parameters: allParams,
      },
    });
  }
}
