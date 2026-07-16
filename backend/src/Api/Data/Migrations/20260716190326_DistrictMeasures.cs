using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace GovTech.Api.Data.Migrations
{
    /// <inheritdoc />
    public partial class DistrictMeasures : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_PreventiveMeasures_Settlements_SettlementId",
                table: "PreventiveMeasures");

            migrationBuilder.AlterColumn<int>(
                name: "SettlementId",
                table: "PreventiveMeasures",
                type: "integer",
                nullable: true,
                oldClrType: typeof(int),
                oldType: "integer");

            migrationBuilder.AddColumn<string>(
                name: "DistrictId",
                table: "PreventiveMeasures",
                type: "character varying(100)",
                maxLength: 100,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "DistrictName",
                table: "PreventiveMeasures",
                type: "character varying(300)",
                maxLength: 300,
                nullable: true);

            migrationBuilder.CreateIndex(
                name: "IX_PreventiveMeasures_Module_DistrictId",
                table: "PreventiveMeasures",
                columns: new[] { "Module", "DistrictId" });

            migrationBuilder.AddForeignKey(
                name: "FK_PreventiveMeasures_Settlements_SettlementId",
                table: "PreventiveMeasures",
                column: "SettlementId",
                principalTable: "Settlements",
                principalColumn: "Id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_PreventiveMeasures_Settlements_SettlementId",
                table: "PreventiveMeasures");

            migrationBuilder.DropIndex(
                name: "IX_PreventiveMeasures_Module_DistrictId",
                table: "PreventiveMeasures");

            migrationBuilder.DropColumn(
                name: "DistrictId",
                table: "PreventiveMeasures");

            migrationBuilder.DropColumn(
                name: "DistrictName",
                table: "PreventiveMeasures");

            migrationBuilder.AlterColumn<int>(
                name: "SettlementId",
                table: "PreventiveMeasures",
                type: "integer",
                nullable: false,
                defaultValue: 0,
                oldClrType: typeof(int),
                oldType: "integer",
                oldNullable: true);

            migrationBuilder.AddForeignKey(
                name: "FK_PreventiveMeasures_Settlements_SettlementId",
                table: "PreventiveMeasures",
                column: "SettlementId",
                principalTable: "Settlements",
                principalColumn: "Id",
                onDelete: ReferentialAction.Cascade);
        }
    }
}
